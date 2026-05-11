import sys
from datetime import datetime, timezone
from pathlib import Path

import anndata as ad
from sqlalchemy import delete, select

from app.database import SessionLocal, init_db
from app.models import PopulationGroup, Sample, SampleDataAsset, SingleCellCell

DEFAULT_GROUP_CODE = "plain_low_altitude"


def as_optional_string(value) -> str | None:
    if value is None or str(value) == "nan":
        return None
    return str(value)


def make_jsonable(value):
    if value is None or str(value) == "nan":
        return None
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def metadata_dict(source: dict | None) -> dict:
    if not source:
        return {}
    return {str(key): make_jsonable(value) for key, value in source.items()}


def infer_sample_code(file_path: Path, adata) -> str:
    obs_df = adata.obs.copy()
    if "sample_id" not in obs_df.columns:
        return file_path.stem

    values = [as_optional_string(value) for value in obs_df["sample_id"].tolist()]
    unique_values = sorted({value for value in values if value})
    if len(unique_values) > 1:
        raise ValueError(f"{file_path.name}: expected exactly one unique sample_id, found {unique_values}")
    if unique_values:
        return unique_values[0]
    return file_path.stem


def infer_sample_metadata(
    file_path: Path,
    adata,
    sample_id_override: str | None = None,
    sample_code_override: str | None = None,
) -> dict:
    dataset_meta = metadata_dict(dict(adata.uns.get("dataset_metadata", {})))
    sample_meta = metadata_dict(dict(adata.uns.get("sample_metadata", {})))
    sample_code = sample_code_override or sample_meta.get("sample_code") or dataset_meta.get("sample_code") or infer_sample_code(file_path, adata)
    return {
        "sample_id": sample_id_override or sample_meta.get("sample_id") or dataset_meta.get("sample_id") or sample_code,
        "sample_code": sample_code,
        "subject_id": sample_meta.get("subject_id") or dataset_meta.get("subject_id"),
        "study_id": sample_meta.get("study_id") or dataset_meta.get("study_id"),
        "title": sample_meta.get("title") or dataset_meta.get("title") or sample_code.replace("_", " ").title(),
        "description": sample_meta.get("description")
        or dataset_meta.get("description")
        or f"Ingested from {file_path.name}",
        "species": sample_meta.get("species") or dataset_meta.get("species") or "human",
        "collection_site": sample_meta.get("collection_site") or dataset_meta.get("collection_site"),
        "group_code": sample_meta.get("group_code")
        or sample_meta.get("population_group_code")
        or dataset_meta.get("group_code")
        or dataset_meta.get("population_group_code")
        or DEFAULT_GROUP_CODE,
        "dataset_metadata": dataset_meta,
        "sample_metadata": sample_meta,
    }


def build_cell_rows(asset_id: int, obs_df):
    rows = []
    for obs_index, (_, row) in enumerate(obs_df.iterrows()):
        metadata = {
            column: make_jsonable(value)
            for column, value in row.items()
            if column not in {"sample_id", "cell_type", "cluster"}
        }
        rows.append(
            SingleCellCell(
                asset_id=asset_id,
                obs_index=obs_index,
                cell_type=as_optional_string(row.get("cell_type")),
                cluster=as_optional_string(row.get("cluster")),
                sample_barcode=as_optional_string(row.get("sample_id")) or str(obs_df.index[obs_index]),
                metadata_json=metadata,
            )
        )
    return rows


def upsert_sample(session, file_path: Path, adata, metadata: dict) -> Sample:
    group = session.execute(
        select(PopulationGroup).where(PopulationGroup.group_code == metadata["group_code"])
    ).scalar_one_or_none()
    if not group:
        raise ValueError(f"Unknown group_code: {metadata['group_code']}")

    obs_df = adata.obs.copy()
    first_row = obs_df.iloc[0].to_dict() if len(obs_df.index) else {}
    sample_metadata = {
        **metadata["dataset_metadata"],
        **metadata["sample_metadata"],
        **{
            key: make_jsonable(value)
            for key, value in first_row.items()
            if key not in {"sample_id", "cell_type", "cluster"}
        },
    }

    sample = session.get(Sample, metadata["sample_id"])
    if not sample:
        sample = Sample(
            sample_id=metadata["sample_id"],
            sample_code=metadata["sample_code"],
            group_id=group.group_id,
            subject_id=metadata["subject_id"],
            study_id=metadata["study_id"],
            title=metadata["title"],
            description=metadata["description"],
            species=metadata["species"],
            tissue=as_optional_string(first_row.get("tissue")),
            condition=as_optional_string(first_row.get("condition")),
            collection_site=metadata["collection_site"],
            metadata_json=sample_metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(sample)
    else:
        sample.sample_code = metadata["sample_code"]
        sample.group_id = group.group_id
        sample.subject_id = metadata["subject_id"]
        sample.study_id = metadata["study_id"]
        sample.title = metadata["title"]
        sample.description = metadata["description"]
        sample.species = metadata["species"]
        sample.tissue = as_optional_string(first_row.get("tissue"))
        sample.condition = as_optional_string(first_row.get("condition"))
        sample.collection_site = metadata["collection_site"]
        sample.metadata_json = sample_metadata
    session.flush()
    return sample


def ingest_file(
    file_path: Path,
    stored_file_path: str | None = None,
    group_code: str | None = None,
    sample_id_override: str | None = None,
    sample_code_override: str | None = None,
) -> None:
    adata = ad.read_h5ad(file_path)
    metadata = infer_sample_metadata(
        file_path,
        adata,
        sample_id_override=sample_id_override,
        sample_code_override=sample_code_override,
    )
    if group_code:
        metadata["group_code"] = group_code

    obs_df = adata.obs.copy()
    sample_id_values = {as_optional_string(value) for value in obs_df.get("sample_id", []) if as_optional_string(value)}
    if len(sample_id_values) > 1:
        raise ValueError(f"{file_path.name}: expected one sample per h5ad, found {sorted(sample_id_values)}")

    session = SessionLocal()
    try:
        sample = upsert_sample(session, file_path, adata, metadata)
        asset = session.execute(
            select(SampleDataAsset).where(
                SampleDataAsset.sample_id == sample.sample_id,
                SampleDataAsset.modality == "single_cell_h5ad",
            )
        ).scalar_one_or_none()
        asset_metadata = {
            "n_obs": int(adata.n_obs),
            "n_vars": int(adata.n_vars),
            "source_path": str(file_path.resolve()),
            "dataset_metadata": metadata["dataset_metadata"],
            "sample_metadata": metadata["sample_metadata"],
        }

        if asset:
            session.execute(delete(SingleCellCell).where(SingleCellCell.asset_id == asset.asset_id))
            asset.file_format = "h5ad"
            asset.file_path = stored_file_path or str(file_path.resolve())
            asset.file_name = file_path.name
            asset.size_bytes = file_path.stat().st_size if file_path.exists() else None
            asset.is_active = True
            asset.metadata_json = asset_metadata
        else:
            asset = SampleDataAsset(
                sample_id=sample.sample_id,
                modality="single_cell_h5ad",
                file_format="h5ad",
                file_path=stored_file_path or str(file_path.resolve()),
                file_name=file_path.name,
                size_bytes=file_path.stat().st_size if file_path.exists() else None,
                checksum=None,
                source_url=None,
                is_active=True,
                metadata_json=asset_metadata,
                created_at=datetime.now(timezone.utc),
            )
            session.add(asset)
            session.flush()

        session.add_all(build_cell_rows(asset.asset_id, obs_df))
        session.commit()
        print(f"Ingested sample {sample.sample_id} ({adata.n_obs} cells)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    args = sys.argv[1:]
    stored_prefix: str | None = None
    group_code: str | None = None
    excluded_files: set[str] = set()
    cleaned_args: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--stored-prefix":
            if i + 1 >= len(args):
                raise SystemExit("Missing value for --stored-prefix")
            stored_prefix = args[i + 1]
            i += 2
            continue
        if args[i] == "--group-code":
            if i + 1 >= len(args):
                raise SystemExit("Missing value for --group-code")
            group_code = args[i + 1]
            i += 2
            continue
        if args[i] == "--exclude-file":
            if i + 1 >= len(args):
                raise SystemExit("Missing value for --exclude-file")
            excluded_files.add(args[i + 1])
            i += 2
            continue
        cleaned_args.append(args[i])
        i += 1

    target = Path(cleaned_args[0]) if cleaned_args else Path("/data/h5ad")
    init_db()
    if target.is_file():
        if target.name in excluded_files:
            print(f"Skipping excluded file {target.name}")
            return
        stored_file_path = None
        if stored_prefix:
            stored_file_path = str(Path(stored_prefix) / target.name)
        ingest_file(target, stored_file_path=stored_file_path, group_code=group_code)
        return

    for file_path in sorted(target.glob("*.h5ad")):
        if file_path.name in excluded_files:
            print(f"Skipping excluded file {file_path.name}")
            continue
        stored_file_path = None
        if stored_prefix:
            relative = file_path.relative_to(target)
            stored_file_path = str(Path(stored_prefix) / relative)
        ingest_file(file_path, stored_file_path=stored_file_path, group_code=group_code)


if __name__ == "__main__":
    main()
