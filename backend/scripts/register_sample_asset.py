import argparse
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import PopulationGroup, Sample, SampleDataAsset


def asset_file_format_for(modality: str, file_path: Path) -> str:
    suffixes = [suffix.lower() for suffix in file_path.suffixes]
    if modality == "fastq":
        if suffixes[-2:] != [".fastq", ".gz"]:
            raise SystemExit("FASTQ assets must use a .fastq.gz file")
        return "fastq.gz"

    if suffixes[-2:] == [".csv", ".gz"] or suffixes[-1:] == [".csv"]:
        return "csv"
    if suffixes[-2:] == [".tsv", ".gz"] or suffixes[-1:] == [".tsv"]:
        return "tsv"
    if suffixes[-2:] == [".txt", ".gz"] or suffixes[-1:] == [".txt"]:
        return "txt"
    raise SystemExit("Bulk asset file_format must resolve to csv, tsv, or txt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a FASTQ or bulk asset for a sample.")
    parser.add_argument("sample_id")
    parser.add_argument("sample_code")
    parser.add_argument("group_code")
    parser.add_argument("modality", choices=["fastq", "bulk"])
    parser.add_argument("file_path")
    parser.add_argument("--subject-id")
    parser.add_argument("--study-id")
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--species", default="human")
    parser.add_argument("--tissue")
    parser.add_argument("--condition")
    parser.add_argument("--collection-site")
    parser.add_argument("--checksum")
    parser.add_argument("--source-url")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    file_path = Path(args.file_path).resolve()
    file_name = file_path.name
    file_format = asset_file_format_for(args.modality, file_path)

    session = SessionLocal()
    try:
        group = session.execute(
            select(PopulationGroup).where(PopulationGroup.group_code == args.group_code)
        ).scalar_one_or_none()
        if not group:
            raise SystemExit(f"Unknown group_code: {args.group_code}")

        sample = session.get(Sample, args.sample_id)
        if not sample:
            sample = Sample(
                sample_id=args.sample_id,
                sample_code=args.sample_code,
                group_id=group.group_id,
                subject_id=args.subject_id,
                study_id=args.study_id,
                title=args.title,
                description=args.description,
                species=args.species,
                tissue=args.tissue,
                condition=args.condition,
                collection_site=args.collection_site,
                metadata_json={},
                created_at=datetime.now(timezone.utc),
            )
            session.add(sample)
            session.flush()
        else:
            sample.sample_code = args.sample_code
            sample.group_id = group.group_id
            sample.subject_id = args.subject_id
            sample.study_id = args.study_id
            sample.title = args.title
            sample.description = args.description
            sample.species = args.species
            sample.tissue = args.tissue
            sample.condition = args.condition
            sample.collection_site = args.collection_site

        asset = session.execute(
            select(SampleDataAsset).where(
                SampleDataAsset.sample_id == sample.sample_id,
                SampleDataAsset.modality == args.modality,
            )
        ).scalar_one_or_none()
        if not asset:
            asset = SampleDataAsset(
                sample_id=sample.sample_id,
                modality=args.modality,
                file_format=file_format,
                file_path=str(file_path),
                file_name=file_name,
                size_bytes=file_path.stat().st_size if file_path.exists() else None,
                checksum=args.checksum,
                source_url=args.source_url,
                is_active=True,
                metadata_json={},
                created_at=datetime.now(timezone.utc),
            )
            session.add(asset)
        else:
            asset.file_format = file_format
            asset.file_path = str(file_path)
            asset.file_name = file_name
            asset.size_bytes = file_path.stat().st_size if file_path.exists() else None
            asset.checksum = args.checksum
            asset.source_url = args.source_url
            asset.is_active = True

        session.commit()
        print(f"Registered {args.modality} asset for sample {sample.sample_id}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
