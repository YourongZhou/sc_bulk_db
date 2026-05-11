import argparse
import csv
import gzip
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import PopulationGroup, Sample, SampleDataAsset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a GEO bulk RNA-seq series as per-sample bulk assets.")
    parser.add_argument("--series-id", default="GSE198533")
    parser.add_argument("--raw-dir", type=Path, default=Path("/data/raw/bulk/GSE198533"))
    parser.add_argument("--counts-path", type=Path, default=None)
    parser.add_argument("--soft-path", type=Path, default=None)
    parser.add_argument("--group-code", default="plain_low_altitude")
    parser.add_argument("--species", default="human")
    return parser.parse_args()


def counts_path_for(raw_dir: Path, series_id: str, override: Path | None) -> Path:
    return override or raw_dir / f"{series_id}_Raw_gene_counts_matrix.csv.gz"


def soft_path_for(raw_dir: Path, series_id: str, override: Path | None) -> Path:
    return override or raw_dir / f"{series_id}_family.soft.gz"


def bulk_file_format_for(path: Path) -> str:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if suffixes[-2:] == [".csv", ".gz"] or suffixes[-1:] == [".csv"]:
        return "csv"
    if suffixes[-2:] == [".tsv", ".gz"] or suffixes[-1:] == [".tsv"]:
        return "tsv"
    if suffixes[-2:] == [".txt", ".gz"] or suffixes[-1:] == [".txt"]:
        return "txt"
    raise SystemExit(f"Unsupported bulk file format for {path}")


def read_sample_titles_from_counts(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    count_columns = [column for column in header if column.endswith("_count")]
    if not count_columns:
        raise ValueError(f"{path}: no *_count columns found")
    return [column.removesuffix("_count") for column in count_columns]


def parse_characteristic(value: str) -> tuple[str, str]:
    if ":" not in value:
        return value.strip().lower(), ""
    key, raw = value.split(":", 1)
    return key.strip().lower(), raw.strip()


def parse_relation_accession(value: str, prefix: str) -> str | None:
    if not value.startswith(prefix):
        return None
    return value.rsplit("=", 1)[-1].strip().split("/")[-1]


def parse_soft_series(path: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    series_meta: dict[str, str] = {}
    sample_rows: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith("^SERIES = "):
                continue
            if line.startswith("!Series_title = "):
                series_meta["title"] = line.removeprefix("!Series_title = ").strip()
                continue
            if line.startswith("!Series_summary = "):
                series_meta["summary"] = line.removeprefix("!Series_summary = ").strip()
                continue
            if line.startswith("!Series_overall_design = "):
                series_meta["overall_design"] = line.removeprefix("!Series_overall_design = ").strip()
                continue

            if line.startswith("^SAMPLE = "):
                if current and current.get("sample_title"):
                    sample_rows[current["sample_title"]] = current
                current = {"sample_geo_accession": line.removeprefix("^SAMPLE = ").strip()}
                continue

            if current is None or not line.startswith("!Sample_"):
                continue

            if line.startswith("!Sample_title = "):
                current["sample_title"] = line.removeprefix("!Sample_title = ").strip()
            elif line.startswith("!Sample_source_name_ch1 = "):
                current["source_name"] = line.removeprefix("!Sample_source_name_ch1 = ").strip()
            elif line.startswith("!Sample_characteristics_ch1 = "):
                key, value = parse_characteristic(line.removeprefix("!Sample_characteristics_ch1 = ").strip())
                current[key] = value
            elif line.startswith("!Sample_relation = "):
                relation = line.removeprefix("!Sample_relation = ").strip()
                sra = parse_relation_accession(relation, "SRA:")
                biosample = parse_relation_accession(relation, "BioSample:")
                if sra:
                    current["sra_accession"] = sra
                if biosample:
                    current["biosample_accession"] = biosample

    if current and current.get("sample_title"):
        sample_rows[current["sample_title"]] = current
    if not sample_rows:
        raise ValueError(f"{path}: failed to parse GEO sample metadata")
    return series_meta, sample_rows


def infer_tissue(source_name: str | None) -> str:
    value = (source_name or "").strip()
    if not value:
        return "PBMC"
    if "pbmc" in value.lower():
        return "PBMC"
    return value


def sample_identity(series_id: str, sample_title: str) -> tuple[str, str]:
    return f"{series_id}:{sample_title}", f"{series_id}_{sample_title}"


def upsert_bulk_sample(
    session,
    *,
    group: PopulationGroup,
    counts_path: Path,
    soft_path: Path,
    series_id: str,
    series_meta: dict[str, str],
    sample_title: str,
    sample_meta: dict[str, str],
    species: str,
    file_format: str,
) -> None:
    sample_id, sample_code = sample_identity(series_id, sample_title)
    condition = sample_meta.get("condition")
    source_name = sample_meta.get("source_name")
    title = sample_title
    description = series_meta.get("title") or series_meta.get("summary") or f"{series_id} bulk RNA-seq sample"
    sample_metadata = {
        "series_id": series_id,
        "series_title": series_meta.get("title"),
        "series_summary": series_meta.get("summary"),
        "series_overall_design": series_meta.get("overall_design"),
        **sample_meta,
    }
    asset_metadata = {
        "series_id": series_id,
        "matrix_path": str(counts_path.resolve()),
        "soft_path": str(soft_path.resolve()),
        "sample_title": sample_title,
        "sample_geo_accession": sample_meta.get("sample_geo_accession"),
        "condition": condition,
        "source_name": source_name,
        "age": sample_meta.get("age"),
        "sex": sample_meta.get("sex"),
    }

    sample = session.get(Sample, sample_id)
    if not sample:
        sample = Sample(
            sample_id=sample_id,
            sample_code=sample_code,
            group_id=group.group_id,
            subject_id=sample_meta.get("sample_geo_accession") or sample_title,
            study_id=series_id,
            title=title,
            description=description,
            species=species,
            tissue=infer_tissue(source_name),
            condition=condition,
            collection_site=source_name,
            metadata_json=sample_metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(sample)
        session.flush()
    else:
        sample.sample_code = sample_code
        sample.group_id = group.group_id
        sample.subject_id = sample_meta.get("sample_geo_accession") or sample_title
        sample.study_id = series_id
        sample.title = title
        sample.description = description
        sample.species = species
        sample.tissue = infer_tissue(source_name)
        sample.condition = condition
        sample.collection_site = source_name
        sample.metadata_json = sample_metadata

    asset = session.execute(
        select(SampleDataAsset).where(
            SampleDataAsset.sample_id == sample_id,
            SampleDataAsset.modality == "bulk",
        )
    ).scalar_one_or_none()
    source_url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={series_id}"
    if not asset:
        asset = SampleDataAsset(
            sample_id=sample_id,
            modality="bulk",
            file_format=file_format,
            file_path=str(counts_path.resolve()),
            file_name=counts_path.name,
            size_bytes=counts_path.stat().st_size if counts_path.exists() else None,
            checksum=None,
            source_url=source_url,
            is_active=True,
            metadata_json=asset_metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(asset)
    else:
        asset.file_format = file_format
        asset.file_path = str(counts_path.resolve())
        asset.file_name = counts_path.name
        asset.size_bytes = counts_path.stat().st_size if counts_path.exists() else None
        asset.source_url = source_url
        asset.is_active = True
        asset.metadata_json = asset_metadata


def main() -> None:
    args = parse_args()
    counts_path = counts_path_for(args.raw_dir, args.series_id, args.counts_path)
    soft_path = soft_path_for(args.raw_dir, args.series_id, args.soft_path)
    file_format = bulk_file_format_for(counts_path)
    sample_titles = read_sample_titles_from_counts(counts_path)
    series_meta, sample_rows = parse_soft_series(soft_path)

    missing = [sample_title for sample_title in sample_titles if sample_title not in sample_rows]
    if missing:
        raise SystemExit(f"Sample metadata missing rows for: {missing}")

    init_db()
    session = SessionLocal()
    try:
        group = session.execute(
            select(PopulationGroup).where(PopulationGroup.group_code == args.group_code)
        ).scalar_one_or_none()
        if not group:
            raise SystemExit(f"Unknown group_code: {args.group_code}")

        for sample_title in sample_titles:
            upsert_bulk_sample(
                session,
                group=group,
                counts_path=counts_path,
                soft_path=soft_path,
                series_id=args.series_id,
                series_meta=series_meta,
                sample_title=sample_title,
                sample_meta=sample_rows[sample_title],
                species=args.species,
                file_format=file_format,
            )
        session.commit()
        print(f"Registered {len(sample_titles)} bulk samples for {args.series_id}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
