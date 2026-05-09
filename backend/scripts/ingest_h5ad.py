import sys
from datetime import datetime
from pathlib import Path

import scanpy as sc
from sqlalchemy import delete

from app.database import SessionLocal, init_db
from app.models import Cell, Dataset, Sample


def infer_dataset_metadata(file_path: Path, adata) -> dict:
    meta = dict(adata.uns.get("dataset_metadata", {}))
    dataset_id = meta.get("dataset_id") or file_path.stem
    return {
        "dataset_id": dataset_id,
        "title": meta.get("title", dataset_id.replace("_", " ").title()),
        "description": meta.get("description", f"Ingested from {file_path.name}"),
        "omics_type": meta.get("omics_type", "unknown"),
        "species": meta.get("species", "unknown"),
    }


def build_sample_rows(dataset_id: str, obs_df):
    rows = []
    if "sample_id" not in obs_df.columns:
        raise ValueError(f"{dataset_id}: adata.obs must contain sample_id")

    for sample_id, frame in obs_df.groupby("sample_id", dropna=False):
        sample_value = str(sample_id) if sample_id is not None else f"{dataset_id}_unknown_sample"
        first = frame.iloc[0]
        metadata = {
            column: None if str(first[column]) == "nan" else str(first[column])
            for column in frame.columns
            if column not in {"sample_id", "cell_type", "cluster"}
        }
        rows.append(
            Sample(
                sample_id=f"{dataset_id}:{sample_value}",
                dataset_id=dataset_id,
                disease=metadata.get("disease"),
                tissue=metadata.get("tissue"),
                condition=metadata.get("condition"),
                metadata_json=metadata,
            )
        )
    return rows


def build_cell_rows(dataset_id: str, obs_df):
    rows = []
    for obs_index, (_, row) in enumerate(obs_df.iterrows()):
        sample_value = row.get("sample_id")
        sample_key = f"{dataset_id}:{sample_value}" if sample_value is not None else None
        metadata = {
            column: None if str(value) == "nan" else str(value)
            for column, value in row.items()
            if column not in {"sample_id", "cell_type", "cluster"}
        }
        rows.append(
            Cell(
                dataset_id=dataset_id,
                obs_index=obs_index,
                sample_id=sample_key,
                cell_type=None if str(row.get("cell_type")) == "nan" else str(row.get("cell_type")),
                cluster=None if str(row.get("cluster")) == "nan" else str(row.get("cluster")),
                metadata_json=metadata,
            )
        )
    return rows


def ingest_file(file_path: Path, stored_file_path: str | None = None) -> None:
    adata = sc.read_h5ad(file_path)
    metadata = infer_dataset_metadata(file_path, adata)
    dataset_id = metadata["dataset_id"]

    obs_df = adata.obs.copy()
    sample_rows = build_sample_rows(dataset_id, obs_df)
    cell_rows = build_cell_rows(dataset_id, obs_df)

    session = SessionLocal()
    try:
        session.execute(delete(Cell).where(Cell.dataset_id == dataset_id))
        session.execute(delete(Sample).where(Sample.dataset_id == dataset_id))
        session.execute(delete(Dataset).where(Dataset.dataset_id == dataset_id))
        session.add(
            Dataset(
                dataset_id=dataset_id,
                title=metadata["title"],
                description=metadata["description"],
                omics_type=metadata["omics_type"],
                species=metadata["species"],
                file_path=stored_file_path or str(file_path.resolve()),
                n_cells=int(adata.n_obs),
                created_at=datetime.utcnow(),
            )
        )
        session.add_all(sample_rows)
        session.add_all(cell_rows)
        session.commit()
        print(f"Ingested {dataset_id} ({adata.n_obs} cells)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/data/h5ad")
    init_db()
    if target.is_file():
        ingest_file(target)
        return

    for file_path in sorted(target.glob("*.h5ad")):
        ingest_file(file_path)


if __name__ == "__main__":
    main()
