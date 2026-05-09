# Portable Run Notes

## What Goes To GitHub

Commit the application code, Docker files, scripts, and documentation. Do not commit downloaded H5AD/count files:
GitHub blocks normal files over 100 MB, and the test CELLxGENE H5AD is about 485 MB.

## Run On Another Machine

1. Install Docker Desktop.
   - Windows: use Docker Desktop with WSL2.
   - Linux: install Docker Engine and Docker Compose.
2. Clone the repository.
3. Start the app:

```bash
docker compose up --build -d
```

4. Open:

```text
http://localhost:8080
```

## Recreate Real Data

Generate manifests first:

```bash
docker compose run --rm backend sh -c "pip install --no-cache-dir -r scripts/download/requirements.txt && python scripts/download/find_cellxgene_pbmc.py"
```

Download selected CELLxGENE datasets:

```bash
docker compose run --rm backend sh -c "pip install --no-cache-dir -r scripts/download/requirements.txt && python scripts/download/find_cellxgene_pbmc.py --download"
```

Preprocess single-cell files:

```bash
docker compose run --rm backend python scripts/preprocess/preprocess_single_cell.py \
  --manifest /data/manifests/single_cell_manifest.csv \
  --raw-dir /data/raw/single_cell \
  --output-dir /data/processed/h5ad \
  --report /data/manifests/single_cell_preprocess_report.csv
```

Bulk recount3 downloads currently require an R environment with `recount3` and `SummarizedExperiment`.
After bulk files are downloaded into `data/raw/bulk`, preprocess them with:

```bash
docker compose run --rm backend python scripts/preprocess/preprocess_bulk_recount3.py \
  --manifest /data/manifests/bulk_manifest.csv \
  --raw-dir /data/raw/bulk \
  --output-dir /data/processed/h5ad \
  --report /data/manifests/bulk_preprocess_report.csv
```

Ingest processed files:

```bash
docker compose run --rm backend python scripts/admin/reset_and_ingest.py \
  --processed-dir /data/processed/h5ad \
  --h5ad-dir /data/h5ad \
  --backup-root /data/backups \
  --stored-prefix /data/processed/h5ad
```

## Migration Rule

The portable source of truth is:

- repository code
- generated/downloaded files under `data/`
- `data/processed/h5ad/*.h5ad`

The PostgreSQL Docker volume is disposable. Rebuild it by rerunning `reset_and_ingest.py`.
