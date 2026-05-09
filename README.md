# Multi-Omics Data Warehouse Prototype

Prototype web demo for browsing multi-omics datasets, filtering by metadata, querying cells across datasets, and lazily reading cell subsets from immutable `.h5ad` files.

## Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL, Scanpy
- Frontend: React + Vite
- Containers: Docker Compose

## Run

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

On startup, the `ingest` service creates a few synthetic `.h5ad` demo datasets in `./data/h5ad` and indexes them into PostgreSQL.

## Project Layout

- `backend/`: FastAPI app, SQLAlchemy models, ingestion scripts
- `frontend/`: React UI
- `data/h5ad/`: immutable `.h5ad` files

## Demo Flow

1. Open the dataset browser.
2. Filter datasets by disease, tissue, or omics type.
3. Open a dataset detail page and inspect metadata.
4. Run a cell query such as `T cell`.
5. Select cells and preview expression values loaded dynamically from the source `.h5ad`.

## Ingestion

To add new datasets:

1. Place a `.h5ad` file in `data/h5ad/`.
2. Ensure `adata.obs` contains `sample_id`, and optionally `cell_type`, `cluster`, `disease`, `tissue`, `condition`.
3. Re-run ingestion:

```bash
docker compose run --rm ingest python scripts/ingest_h5ad.py /data/h5ad
```

The source files remain immutable. PostgreSQL stores metadata and cell indexing only.

## Real Data Workflow

The real-data workflow is manifest-first. Candidate discovery is safe to run; real downloads only happen when
`--download` is passed.

### 1. Discover single-cell candidates

```bash
pip install -r backend/scripts/download/requirements.txt
python backend/scripts/download/find_cellxgene_pbmc.py
```

This writes `data/manifests/single_cell_manifest.csv`. Review the selected rows, then download:

```bash
python backend/scripts/download/find_cellxgene_pbmc.py --download
```

### 2. Discover bulk candidates

Install Bioconductor `recount3` and `SummarizedExperiment` in R, then run:

```bash
Rscript backend/scripts/download/download_recount3_bulk.R
```

This writes `data/manifests/bulk_manifest.csv`. Review the selected rows, then download:

```bash
Rscript backend/scripts/download/download_recount3_bulk.R --download
```

### 3. Preprocess into ingestible H5AD

```bash
python backend/scripts/preprocess/preprocess_single_cell.py
python backend/scripts/preprocess/preprocess_bulk_recount3.py
```

Processed files are written to `data/processed/h5ad/`. Single-cell files are normalized to required metadata fields
and get `X_umap` when possible. Bulk projects are converted to one-row-per-sample H5AD files with `X_pca`.

### 4. Back up demo data, clear indexes, and ingest processed files

When using Docker Compose, run the reset from the backend container so stored H5AD paths use `/data/...`:

```bash
docker compose run --rm backend python scripts/admin/reset_and_ingest.py \
  --processed-dir /data/processed/h5ad \
  --h5ad-dir /data/h5ad \
  --backup-root /data/backups \
  --stored-prefix /data/processed/h5ad
```

The script moves existing `data/h5ad/*.h5ad` files into `data/backups/<timestamp>/h5ad/`, clears the SQL metadata
tables, and ingests every processed H5AD.
