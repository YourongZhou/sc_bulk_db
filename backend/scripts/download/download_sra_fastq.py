import argparse
import csv
import shutil
import subprocess
from urllib.parse import urlparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public FASTQ runs listed in a manifest.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/pbmc_fastq_manifest.csv"),
        help="CSV manifest with run_accession/local_dir columns.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        help="Optional run accessions to restrict the download set.",
    )
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--keep-sra", action="store_true", help="Keep downloaded .sra cache files.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Missing required tool: {name}")
    return path


def run(cmd: list[str], dry_run: bool) -> None:
    print("$", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def existing_fastqs(local_dir: Path, run_accession: str) -> list[Path]:
    return sorted(local_dir.glob(f"{run_accession}*.fastq.gz"))


def maybe_mark_downloaded(row: dict[str, str]) -> bool:
    local_dir = Path(row["local_dir"])
    fastqs = existing_fastqs(local_dir, row["run_accession"])
    return bool(fastqs)


def fetch_ena_fastq_urls(run_accession: str) -> list[str]:
    url = (
        "https://www.ebi.ac.uk/ena/portal/api/filereport"
        f"?accession={run_accession}"
        "&result=read_run"
        "&fields=run_accession,fastq_ftp"
        "&format=tsv"
    )
    result = subprocess.run(
        ["curl", "-L", "-sS", "--fail", url],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"No ENA metadata returned for {run_accession}")
    header = lines[0].split("\t")
    values = lines[1].split("\t")
    record = dict(zip(header, values, strict=False))
    fastq_ftp = record.get("fastq_ftp", "")
    if not fastq_ftp:
        raise RuntimeError(f"No fastq_ftp URLs available for {run_accession}")
    return [f"https://{part}" for part in fastq_ftp.split(";") if part]


def download_from_ena(row: dict[str, str], dry_run: bool) -> None:
    run_accession = row["run_accession"]
    local_dir = Path(row["local_dir"])
    local_dir.mkdir(parents=True, exist_ok=True)
    for fastq_url in fetch_ena_fastq_urls(run_accession):
        filename = Path(urlparse(fastq_url).path).name
        destination = local_dir / filename
        run(
            [
                "curl",
                "-L",
                "--fail",
                "--retry",
                "3",
                "--continue-at",
                "-",
                "-o",
                str(destination),
                fastq_url,
            ],
            dry_run,
        )


def download_row(row: dict[str, str], threads: int, keep_sra: bool, dry_run: bool) -> None:
    _ = threads
    _ = keep_sra
    download_from_ena(row, dry_run)


def load_rows(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(manifest_path: Path, rows: list[dict[str, str]]) -> None:
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = load_rows(args.manifest)
    if not rows:
        raise SystemExit(f"No rows found in {args.manifest}")

    if not args.dry_run:
        require_tool("curl")

    only = set(args.only)
    for row in rows:
        if str(row.get("selected", "")).lower() not in {"true", "1", "yes"}:
            continue
        if only and row["run_accession"] not in only:
            continue
        if maybe_mark_downloaded(row):
            row["downloaded"] = "True"
            row["error"] = ""
            continue
        try:
            download_row(row, args.threads, args.keep_sra, args.dry_run)
            row["downloaded"] = "True"
            row["error"] = ""
        except Exception as exc:  # noqa: BLE001
            row["downloaded"] = "False"
            row["error"] = str(exc)
        write_rows(args.manifest, rows)


if __name__ == "__main__":
    main()
