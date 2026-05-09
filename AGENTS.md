# Project Notes for Agents

## Overview

This repository is a multi-omics data warehouse prototype.

- Backend: FastAPI, SQLAlchemy, PostgreSQL, Scanpy.
- Frontend: React + Vite.
- Data files: immutable `.h5ad` files under `data/h5ad/`.
- PostgreSQL stores searchable metadata and cell row indexes only. Expression matrices and feature names are loaded lazily from the source `.h5ad` file.

## Database Source of Truth

The runtime schema is created by SQLAlchemy from `backend/app/models.py` via `Base.metadata.create_all()` in `backend/app/database.py`.

There is also a static SQL file at `backend/sql/schema.sql`. It matches the table layout, but note one type difference:

- `backend/sql/schema.sql` declares `samples.metadata` and `cells.metadata` as `JSONB`.
- `backend/app/models.py` declares those columns with SQLAlchemy `JSON`.

If the database is created by the running application or ingest service, treat the ORM models as the effective source of truth unless migrations are added later.

## PostgreSQL Connection

Docker Compose defines the default database service:

- Database: `omics_demo`
- User: `omics`
- Password: `omics`
- Host in Compose network: `postgres:5432`
- Host from local machine: `localhost:5432`
- Backend URL in Compose: `postgresql+psycopg://omics:omics@postgres:5432/omics_demo`
- Backend default URL outside Compose: `postgresql+psycopg://omics:omics@localhost:5432/omics_demo`

There is no migration framework in the current repo. Schema changes should update both `backend/app/models.py` and `backend/sql/schema.sql`, plus any ingest/API code affected by the change.

## Tables

### `datasets`

One row per ingested `.h5ad` dataset.

| Column | Type | Null | Key | Notes |
| --- | --- | --- | --- | --- |
| `dataset_id` | `TEXT` | no | PK | Stable dataset identifier. Usually from `adata.uns["dataset_metadata"]["dataset_id"]`, falling back to file stem. |
| `title` | `TEXT` | no |  | Human-readable title. |
| `description` | `TEXT` | no |  | Dataset description. |
| `omics_type` | `TEXT` | no |  | Examples: `scRNA-seq`, `bulk RNA-seq`, `ATAC-seq`, `spatial`, `DNA`. |
| `species` | `TEXT` | no |  | Example values include `human` and `mouse`. |
| `file_path` | `TEXT` | no |  | Absolute path to the source `.h5ad` file as stored during ingestion. |
| `n_cells` | `INTEGER` | no |  | Number of observations in the `.h5ad` object. For bulk/DNA examples this is still stored in the same field. |
| `created_at` | `TIMESTAMP` | no |  | Ingestion timestamp. |

Relationships:

- `Dataset.samples`: one-to-many to `samples`, cascade delete.
- `Dataset.cells`: one-to-many to `cells`, cascade delete.

### `samples`

One row per unique `sample_id` within a dataset.

| Column | Type | Null | Key | Notes |
| --- | --- | --- | --- | --- |
| `sample_id` | `TEXT` | no | PK | Ingest builds this as `{dataset_id}:{sample_value}` to keep sample IDs globally unique. |
| `dataset_id` | `TEXT` | no | FK | References `datasets.dataset_id` with `ON DELETE CASCADE`. |
| `disease` | `TEXT` | yes |  | Copied from `adata.obs["disease"]` when present. |
| `tissue` | `TEXT` | yes |  | Copied from `adata.obs["tissue"]` when present. |
| `condition` | `TEXT` | yes |  | Copied from `adata.obs["condition"]` when present. |
| `metadata` | `JSON` / `JSONB` | no |  | Additional sample-level metadata from the first row in each sample group. ORM attribute name is `metadata_json`. |

Relationships:

- `Sample.dataset`: many-to-one to `datasets`.
- `Sample.cells`: one-to-many to `cells`.

### `cells`

One row per observation in an ingested `.h5ad` dataset.

| Column | Type | Null | Key | Notes |
| --- | --- | --- | --- | --- |
| `dataset_id` | `TEXT` | no | PK, FK | References `datasets.dataset_id` with `ON DELETE CASCADE`. |
| `obs_index` | `INTEGER` | no | PK | Zero-based row position in `adata.obs`; used to load expression rows from `.h5ad`. |
| `sample_id` | `TEXT` | yes | FK | References `samples.sample_id`. No explicit `ON DELETE` rule in ORM. |
| `cell_type` | `TEXT` | yes |  | Copied from `adata.obs["cell_type"]` when present. |
| `cluster` | `TEXT` | yes |  | Copied from `adata.obs["cluster"]` when present. |
| `metadata` | `JSON` / `JSONB` | no |  | Additional observation metadata excluding `sample_id`, `cell_type`, and `cluster`. ORM attribute name is `metadata_json`. |

Primary key:

- Composite primary key: `(dataset_id, obs_index)`.

Relationships:

- `Cell.dataset`: many-to-one to `datasets`.
- `Cell.sample`: many-to-one to `samples`.

## Entity Relationship Summary

```text
datasets.dataset_id
  |-- samples.dataset_id
  |     `-- samples.sample_id
  |
  `-- cells.dataset_id
        `-- cells.sample_id -> samples.sample_id
```

Deleting a dataset cascades to its samples and cells. Cells are ordered and looked up by `(dataset_id, obs_index)`, where `obs_index` maps directly back to the source `.h5ad` observation row.

## Ingestion Flow

Main script: `backend/scripts/ingest_h5ad.py`.

Expected `.h5ad` layout:

- `adata.obs` must contain `sample_id`.
- Optional `adata.obs` columns used directly: `cell_type`, `cluster`, `disease`, `tissue`, `condition`.
- Optional dataset metadata comes from `adata.uns["dataset_metadata"]`:
  - `dataset_id`
  - `title`
  - `description`
  - `omics_type`
  - `species`

Ingestion behavior:

1. Read each `.h5ad` file with Scanpy.
2. Infer dataset metadata.
3. Build one `samples` row per unique `adata.obs["sample_id"]`.
4. Build one `cells` row per observation row.
5. Delete existing rows for the same `dataset_id`.
6. Insert the replacement dataset, samples, and cells in one transaction.

The ingest service in `docker-compose.yml` runs:

```bash
python scripts/create_demo_data.py &&
python scripts/ingest_h5ad.py /data/h5ad
```

## API Usage of the Database

Current backend endpoints use the schema as follows:

- `GET /datasets`: lists datasets and filters by `disease`, `tissue`, `condition`, and `omics_type`.
- `GET /datasets/{dataset_id}`: returns one dataset, sample count, sample preview, and facet values.
- `GET /cells`: searches cells by `cell_type`, `disease`, `tissue`, and/or `dataset_id`.
- `POST /cells/data`: validates cell indices, opens the dataset `file_path`, and returns expression rows from the `.h5ad` file.
- `GET /metadata/options`: returns distinct diseases, tissues, and omics types.

## Practical Notes

- Do not store full expression matrices in PostgreSQL with the current design.
- Keep `file_path` valid from the backend container's point of view, because `/cells/data` opens that path directly.
- When adding metadata fields, decide whether they need first-class columns for filtering or should remain inside the JSON `metadata` payload.
- There are currently no explicit indexes beyond primary keys and foreign keys. Add indexes before scaling filters or cell search to larger datasets.
- Because `samples.sample_id` is globally unique by construction, preserve the `{dataset_id}:{raw_sample_id}` convention unless the relationship model is changed.
