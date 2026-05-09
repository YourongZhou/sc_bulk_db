import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import delete

from app.database import SessionLocal, init_db
from app.models import Cell, Dataset, Sample
from scripts.ingest_h5ad import ingest_file


def backup_h5ad_dir(h5ad_dir: Path, backup_root: Path) -> Path | None:
    files = sorted(h5ad_dir.glob("*.h5ad"))
    if not files:
        return None
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / timestamp / "h5ad"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for file_path in files:
        shutil.move(str(file_path), backup_dir / file_path.name)
    return backup_dir


def clear_database() -> None:
    init_db()
    session = SessionLocal()
    try:
        session.execute(delete(Cell))
        session.execute(delete(Sample))
        session.execute(delete(Dataset))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def stored_path_for(file_path: Path, processed_dir: Path, stored_prefix: str | None) -> str | None:
    if not stored_prefix:
        return None
    relative = file_path.relative_to(processed_dir)
    return str(Path(stored_prefix) / relative)


def update_manifest_status(manifest_path: Path, processed_paths: set[str]) -> None:
    if not manifest_path.exists():
        return
    manifest = pd.read_csv(manifest_path)
    path_columns = [column for column in ["processed_path", "local_path"] if column in manifest.columns]
    if not path_columns:
        return
    manifest["ingested"] = manifest.apply(
        lambda row: any(str(row.get(column, "")) in processed_paths for column in path_columns),
        axis=1,
    )
    manifest.to_csv(manifest_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up demo H5AD files, clear DB indexes, and ingest processed H5AD.")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/h5ad"))
    parser.add_argument("--h5ad-dir", type=Path, default=Path("data/h5ad"))
    parser.add_argument("--backup-root", type=Path, default=Path("data/backups"))
    parser.add_argument("--stored-prefix", default="/data/processed/h5ad")
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        default=[
            Path("data/manifests/single_cell_manifest.csv"),
            Path("data/manifests/bulk_manifest.csv"),
            Path("data/manifests/single_cell_preprocess_report.csv"),
            Path("data/manifests/bulk_preprocess_report.csv"),
        ],
    )
    parser.add_argument("--skip-backup", action="store_true")
    args = parser.parse_args()

    if not args.skip_backup:
        backup_dir = backup_h5ad_dir(args.h5ad_dir, args.backup_root)
        if backup_dir:
            print(f"Backed up existing H5AD files to {backup_dir}")

    clear_database()
    processed_files = sorted(args.processed_dir.glob("*.h5ad"))
    if not processed_files:
        raise SystemExit(f"No processed H5AD files found in {args.processed_dir}")

    ingested_paths: set[str] = set()
    for file_path in processed_files:
        stored_file_path = stored_path_for(file_path, args.processed_dir, args.stored_prefix)
        ingest_file(file_path, stored_file_path=stored_file_path)
        ingested_paths.add(str(file_path))

    for manifest_path in args.manifest:
        update_manifest_status(manifest_path, ingested_paths)

    print(f"Ingested {len(processed_files)} processed H5AD files")


if __name__ == "__main__":
    main()
