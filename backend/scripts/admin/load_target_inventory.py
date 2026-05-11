import csv
import gzip
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anndata as ad
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal, init_db
from app.models import PopulationGroup, Sample, SampleDataAsset, SingleCellCell
from scripts.ingest_h5ad import ingest_file


GROUP_CODE_PLATEAU = "plateau_high_cold"
GROUP_CODE_TROPICAL = "tropical_heat_tolerant"
GROUP_CODE_AMS = "plain_ams_patient"
GROUP_CODE_LOW = "plain_low_altitude"

RNA_SEQ_SOURCE_DIRS = [
    Path("/data/single_cell/processed_ingest_v3"),
    Path("/data/single_cell/processed_pbmc_atlas_6_time0"),
]

RNA_SEQ_GROUP_SEQUENCE = (
    [GROUP_CODE_PLATEAU] * 6
    + [GROUP_CODE_TROPICAL] * 6
    + [GROUP_CODE_AMS] * 2
    + [GROUP_CODE_LOW] * 14
)
FASTQ_GROUP_SEQUENCE = [GROUP_CODE_PLATEAU] * 3 + [GROUP_CODE_TROPICAL] * 3 + [GROUP_CODE_AMS] * 2 + [GROUP_CODE_LOW] * 7
DISPLAY_MODALITY_NAMES = {
    "single_cell_h5ad": "RNA-seq",
    "bulk": "bulk",
    "fastq": "FASTQ",
}
GROUP_DESCRIPTION_TEMPLATES = {
    GROUP_CODE_PLATEAU: "来自高原高寒居住环境人群的样本，用于分析长期高海拔寒冷环境下的人群分子特征。",
    GROUP_CODE_TROPICAL: "来自热带高温居住环境人群的样本，用于分析长期热湿环境下的人群分子特征。",
    GROUP_CODE_AMS: "来自平原居住环境且出现高原反应人群的样本，用于分析环境转换后的应激与适应特征。",
    GROUP_CODE_LOW: "来自平原低海拔居住环境人群的样本，用作不同居住环境人群对比中的参考队列。",
}


def clear_database() -> None:
    session = SessionLocal()
    try:
        session.execute(delete(SingleCellCell))
        session.execute(delete(SampleDataAsset))
        session.execute(delete(Sample))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def modality_summary(modalities: list[str]) -> str:
    labels = [DISPLAY_MODALITY_NAMES.get(modality, modality) for modality in modalities]
    if not labels:
        return "元数据"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} 和 {labels[1]}"
    return f"{'、'.join(labels[:-1])} 和 {labels[-1]}"


def sample_description(group_code: str, modalities: list[str]) -> str:
    base = GROUP_DESCRIPTION_TEMPLATES.get(
        group_code,
        "来自不同居住环境人群对比队列的样本，用于分析环境差异相关的分子特征。",
    )
    return f"{base} 该样本当前提供 {modality_summary(modalities)} 数据。"


def apply_catalog_titles_and_descriptions() -> None:
    session = SessionLocal()
    try:
        samples = (
            session.execute(
                select(Sample)
                .options(selectinload(Sample.assets), selectinload(Sample.group))
                .order_by(Sample.created_at.desc(), Sample.sample_id)
            )
            .scalars()
            .unique()
            .all()
        )
        for index, sample in enumerate(samples, start=1):
            modalities = sorted(asset.modality for asset in sample.assets if asset.is_active)
            sample.title = f"Sample {index}"
            sample.description = sample_description(sample.group.group_code, modalities)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def group_map(session) -> dict[str, PopulationGroup]:
    groups = session.execute(select(PopulationGroup)).scalars().all()
    return {group.group_code: group for group in groups}


def upsert_asset(
    session,
    *,
    sample: Sample,
    modality: str,
    file_format: str,
    file_path: Path,
    source_url: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    asset = session.execute(
        select(SampleDataAsset).where(
            SampleDataAsset.sample_id == sample.sample_id,
            SampleDataAsset.modality == modality,
        )
    ).scalar_one_or_none()
    payload = metadata_json or {}
    if not asset:
        asset = SampleDataAsset(
            sample_id=sample.sample_id,
            modality=modality,
            file_format=file_format,
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            size_bytes=file_path.stat().st_size if file_path.exists() else None,
            checksum=None,
            source_url=source_url,
            is_active=True,
            metadata_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        session.add(asset)
    else:
        asset.file_format = file_format
        asset.file_path = str(file_path.resolve())
        asset.file_name = file_path.name
        asset.size_bytes = file_path.stat().st_size if file_path.exists() else None
        asset.source_url = source_url
        asset.is_active = True
        asset.metadata_json = payload


def build_pseudobulk_table(h5ad_path: Path, output_path: Path) -> tuple[int, int]:
    adata = ad.read_h5ad(h5ad_path)
    matrix = adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X
    summed = matrix.sum(axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["gene_id", "expression"])
        for gene_id, value in zip(adata.var_names.tolist(), summed.tolist(), strict=False):
            writer.writerow([str(gene_id), float(value)])
    return int(adata.n_obs), int(adata.n_vars)


def single_cell_source_files() -> list[Path]:
    files: list[Path] = []
    for base_dir in RNA_SEQ_SOURCE_DIRS:
        current = sorted(base_dir.glob("*.h5ad"))
        if not current:
            raise SystemExit(f"No single-cell files found in {base_dir}")
        files.extend(current)
    if len(files) != len(RNA_SEQ_GROUP_SEQUENCE):
        raise SystemExit(
            f"Expected {len(RNA_SEQ_GROUP_SEQUENCE)} total single-cell files from {RNA_SEQ_SOURCE_DIRS}, found {len(files)}"
        )
    return files


def load_rna_seq_and_pseudobulk() -> None:
    files = single_cell_source_files()

    pseudobulk_dir = Path("/data/generated/pseudobulk")
    for index, file_path in enumerate(files, start=1):
        sample_id = f"rna_{file_path.stem}"
        sample_code = sample_id
        group_code = RNA_SEQ_GROUP_SEQUENCE[index - 1]
        ingest_file(
            file_path,
            stored_file_path=str(file_path.resolve()),
            group_code=group_code,
            sample_id_override=sample_id,
            sample_code_override=sample_code,
        )

        output_path = pseudobulk_dir / f"{sample_code}.tsv"
        n_obs, n_vars = build_pseudobulk_table(file_path, output_path)
        session = SessionLocal()
        try:
            sample = session.get(Sample, sample_id)
            if not sample:
                raise SystemExit(f"Failed to load sample {sample_id} from {file_path}")
            upsert_asset(
                session,
                sample=sample,
                modality="bulk",
                file_format="tsv",
                file_path=output_path,
                metadata_json={
                    "derived_from": str(file_path.resolve()),
                    "aggregation": "sum_over_cells",
                    "source_modality": "single_cell_h5ad",
                    "n_obs": n_obs,
                    "n_vars": n_vars,
                },
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def parse_gse198533_samples(soft_path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    with gzip.open(soft_path, "rt", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith("^SAMPLE = "):
                if current and current.get("sample_title"):
                    rows[current["sample_title"]] = current
                current = {"sample_geo_accession": line.removeprefix("^SAMPLE = ").strip()}
                continue
            if current is None or not line.startswith("!Sample_"):
                continue
            if line.startswith("!Sample_title = "):
                current["sample_title"] = line.removeprefix("!Sample_title = ").strip()
            elif line.startswith("!Sample_source_name_ch1 = "):
                current["source_name"] = line.removeprefix("!Sample_source_name_ch1 = ").strip()
            elif line.startswith("!Sample_characteristics_ch1 = "):
                payload = line.removeprefix("!Sample_characteristics_ch1 = ").strip()
                if ":" in payload:
                    key, value = payload.split(":", 1)
                    current[key.strip().lower()] = value.strip()
            elif line.startswith("!Sample_relation = "):
                relation = line.removeprefix("!Sample_relation = ").strip()
                if relation.startswith("SRA:"):
                    current["sra_accession"] = relation.rsplit("=", 1)[-1].strip().split("/")[-1]
                elif relation.startswith("BioSample:"):
                    current["biosample_accession"] = relation.rsplit("=", 1)[-1].strip().split("/")[-1]
    if current and current.get("sample_title"):
        rows[current["sample_title"]] = current
    return rows


def register_actual_bulk_samples(counts_path: Path, soft_path: Path) -> None:
    samples = parse_gse198533_samples(soft_path)
    session = SessionLocal()
    try:
        groups = group_map(session)
        for sample_title, metadata in samples.items():
            condition = metadata.get("condition", "")
            group_code = GROUP_CODE_AMS if "BD" in condition else GROUP_CODE_LOW
            group = groups[group_code]
            sample_id = f"GSE198533:{sample_title}"
            sample_code = f"GSE198533_{sample_title}"
            sample = session.get(Sample, sample_id)
            if not sample:
                sample = Sample(
                    sample_id=sample_id,
                    sample_code=sample_code,
                    group_id=group.group_id,
                    subject_id=metadata.get("sample_geo_accession") or sample_title,
                    study_id="GSE198533",
                    title=sample_title,
                    description="mRNA expression profiling of PBMCs from Behcet’s disease",
                    species="human",
                    tissue="PBMC",
                    condition=condition,
                    collection_site=metadata.get("source_name"),
                    metadata_json={"series_id": "GSE198533", **metadata},
                    created_at=datetime.now(timezone.utc),
                )
                session.add(sample)
                session.flush()
            else:
                sample.group_id = group.group_id
                sample.subject_id = metadata.get("sample_geo_accession") or sample_title
                sample.study_id = "GSE198533"
                sample.title = sample_title
                sample.description = "mRNA expression profiling of PBMCs from Behcet’s disease"
                sample.species = "human"
                sample.tissue = "PBMC"
                sample.condition = condition
                sample.collection_site = metadata.get("source_name")
                sample.metadata_json = {"series_id": "GSE198533", **metadata}

            upsert_asset(
                session,
                sample=sample,
                modality="bulk",
                file_format="csv",
                file_path=counts_path,
                source_url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE198533",
                metadata_json={
                    "series_id": "GSE198533",
                    "sample_title": sample_title,
                    "sample_geo_accession": metadata.get("sample_geo_accession"),
                    "condition": condition,
                    "source_name": metadata.get("source_name"),
                    "age": metadata.get("age"),
                    "sex": metadata.get("sex"),
                    "biosample_accession": metadata.get("biosample_accession"),
                    "sra_accession": metadata.get("sra_accession"),
                    "matrix_path": str(counts_path.resolve()),
                    "soft_path": str(soft_path.resolve()),
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def first_fastq_file(local_dir: Path) -> Path:
    candidates = sorted(local_dir.glob("*.fastq.gz"))
    if not candidates:
        raise SystemExit(f"No FASTQ files found in {local_dir}")
    return candidates[0]


def resolve_manifest_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path

    candidates = [Path.cwd() / path]
    if path.parts and path.parts[0] == "data":
        candidates.insert(0, Path("/") / path)
    else:
        candidates.append(Path("/data") / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def register_fastq_samples(manifest_path: Path) -> None:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("selected", "").lower() == "true"]

    if len(rows) != len(FASTQ_GROUP_SEQUENCE):
        raise SystemExit(f"Expected {len(FASTQ_GROUP_SEQUENCE)} selected FASTQ rows, found {len(rows)}")

    session = SessionLocal()
    try:
        groups = group_map(session)
        for row, group_code in zip(rows, FASTQ_GROUP_SEQUENCE, strict=True):
            file_path = first_fastq_file(resolve_manifest_path(row["local_dir"]))
            sample_id = row["dataset_id"]
            sample = session.get(Sample, sample_id)
            if not sample:
                sample = Sample(
                    sample_id=sample_id,
                    sample_code=row["dataset_id"],
                    group_id=groups[group_code].group_id,
                    subject_id=row.get("biosample") or row.get("geo_accession") or row["run_accession"],
                    study_id=row.get("sra_experiment"),
                    title=row.get("run_accession") or row["dataset_id"],
                    description=row.get("notes") or row["dataset_id"],
                    species="human",
                    tissue=row.get("tissue"),
                    condition="FASTQ",
                    collection_site=row.get("cell_type"),
                    metadata_json=row,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(sample)
                session.flush()
            else:
                sample.group_id = groups[group_code].group_id
                sample.subject_id = row.get("biosample") or row.get("geo_accession") or row["run_accession"]
                sample.study_id = row.get("sra_experiment")
                sample.title = row.get("run_accession") or row["dataset_id"]
                sample.description = row.get("notes") or row["dataset_id"]
                sample.species = "human"
                sample.tissue = row.get("tissue")
                sample.condition = "FASTQ"
                sample.collection_site = row.get("cell_type")
                sample.metadata_json = row

            upsert_asset(
                session,
                sample=sample,
                modality="fastq",
                file_format="fastq.gz",
                file_path=file_path,
                source_url=row.get("source_url"),
                metadata_json={
                    "run_accession": row.get("run_accession"),
                    "library_layout": row.get("library_layout"),
                    "estimated_download_mb": row.get("estimated_download_mb"),
                    "local_dir": row.get("local_dir"),
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def print_summary() -> None:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(PopulationGroup.group_code, SampleDataAsset.modality)
            .join(Sample, Sample.group_id == PopulationGroup.group_id)
            .join(SampleDataAsset, SampleDataAsset.sample_id == Sample.sample_id)
        ).all()
        counts = Counter(rows)
        for group_code in [GROUP_CODE_PLATEAU, GROUP_CODE_TROPICAL, GROUP_CODE_AMS, GROUP_CODE_LOW]:
            print(
                group_code,
                {
                    "rna_seq": counts[(group_code, "single_cell_h5ad")],
                    "bulk": counts[(group_code, "bulk")],
                    "fastq": counts[(group_code, "fastq")],
                },
            )
    finally:
        session.close()


def main() -> None:
    init_db()
    clear_database()
    load_rna_seq_and_pseudobulk()
    register_actual_bulk_samples(
        Path("/data/raw/bulk/GSE198533/GSE198533_Raw_gene_counts_matrix.csv.gz"),
        Path("/data/raw/bulk/GSE198533/GSE198533_family.soft.gz"),
    )
    register_fastq_samples(Path("/data/manifests/pbmc_fastq_manifest.csv"))
    apply_catalog_titles_and_descriptions()
    print_summary()


if __name__ == "__main__":
    main()
