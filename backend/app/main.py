from collections import defaultdict
from pathlib import Path

import scanpy as sc
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import Cell, Dataset, Sample
from app.schemas import (
    CellDataRequest,
    CellDataResponse,
    CellResult,
    DatasetDetail,
    DatasetSummary,
    EmbeddingPoint,
    EmbeddingResponse,
)

app = FastAPI(title="Multi-Omics Data Warehouse Prototype", version="0.1.0")

EMBEDDING_METADATA_KEYS = {
    "disease",
    "tissue",
    "condition",
    "assay",
    "donor_id",
    "sex",
    "development_stage",
    "recount3_project",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def build_dataset_query(
    disease: str | None,
    tissue: str | None,
    condition: str | None,
    omics_type: str | None,
) -> Select[tuple[Dataset]]:
    stmt = select(Dataset).distinct()
    if disease or tissue or condition:
        stmt = stmt.join(Sample)
    if disease:
        stmt = stmt.where(Sample.disease.ilike(f"%{disease}%"))
    if tissue:
        stmt = stmt.where(Sample.tissue.ilike(f"%{tissue}%"))
    if condition:
        stmt = stmt.where(Sample.condition.ilike(f"%{condition}%"))
    if omics_type:
        stmt = stmt.where(Dataset.omics_type.ilike(f"%{omics_type}%"))
    return stmt.order_by(Dataset.created_at.desc(), Dataset.dataset_id)


def collect_dataset_facets(db: Session, dataset_ids: list[str]) -> dict[str, dict[str, list[str]]]:
    facet_map: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"disease_values": set(), "tissue_values": set(), "condition_values": set()}
    )
    if not dataset_ids:
        return {}

    rows = db.execute(
        select(Sample.dataset_id, Sample.disease, Sample.tissue, Sample.condition).where(
            Sample.dataset_id.in_(dataset_ids)
        )
    ).all()
    for dataset_id, disease, tissue, condition in rows:
        if disease:
            facet_map[dataset_id]["disease_values"].add(disease)
        if tissue:
            facet_map[dataset_id]["tissue_values"].add(tissue)
        if condition:
            facet_map[dataset_id]["condition_values"].add(condition)

    return {
        dataset_id: {key: sorted(values) for key, values in facets.items()}
        for dataset_id, facets in facet_map.items()
    }


def jsonable(value):
    if value is None or str(value) == "nan":
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)


@app.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(
    disease: str | None = Query(default=None),
    tissue: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    omics_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DatasetSummary]:
    datasets = db.execute(build_dataset_query(disease, tissue, condition, omics_type)).scalars().all()
    facets = collect_dataset_facets(db, [dataset.dataset_id for dataset in datasets])
    return [
        DatasetSummary(
            dataset_id=dataset.dataset_id,
            title=dataset.title,
            description=dataset.description,
            omics_type=dataset.omics_type,
            species=dataset.species,
            n_cells=dataset.n_cells,
            created_at=dataset.created_at,
            disease_values=facets.get(dataset.dataset_id, {}).get("disease_values", []),
            tissue_values=facets.get(dataset.dataset_id, {}).get("tissue_values", []),
            condition_values=facets.get(dataset.dataset_id, {}).get("condition_values", []),
        )
        for dataset in datasets
    ]


@app.get("/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetDetail:
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    sample_rows = (
        db.execute(
            select(Sample).where(Sample.dataset_id == dataset_id).order_by(Sample.sample_id).limit(10)
        )
        .scalars()
        .all()
    )
    facets = collect_dataset_facets(db, [dataset_id]).get(dataset_id, {})

    return DatasetDetail(
        dataset_id=dataset.dataset_id,
        title=dataset.title,
        description=dataset.description,
        omics_type=dataset.omics_type,
        species=dataset.species,
        n_cells=dataset.n_cells,
        created_at=dataset.created_at,
        disease_values=facets.get("disease_values", []),
        tissue_values=facets.get("tissue_values", []),
        condition_values=facets.get("condition_values", []),
        file_path=dataset.file_path,
        sample_count=len(dataset.samples),
        sample_preview=[
            {
                "sample_id": sample.sample_id,
                "disease": sample.disease,
                "tissue": sample.tissue,
                "condition": sample.condition,
            }
            for sample in sample_rows
        ],
    )


@app.get("/datasets/{dataset_id}/embedding", response_model=EmbeddingResponse)
def get_dataset_embedding(
    dataset_id: str,
    basis: str | None = Query(default=None, pattern="^(umap|pca)$"),
    max_points: int = Query(default=5000, ge=100, le=50000),
    db: Session = Depends(get_db),
) -> EmbeddingResponse:
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    requested_basis = basis or ("pca" if dataset.omics_type.lower().startswith("bulk") else "umap")
    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Source h5ad file not found")

    adata = sc.read_h5ad(file_path, backed="r")
    available_bases = sorted(key.replace("X_", "") for key in adata.obsm.keys() if key.startswith("X_"))
    obsm_key = f"X_{requested_basis}"
    if obsm_key not in adata.obsm:
        return EmbeddingResponse(
            dataset_id=dataset_id,
            basis=requested_basis,
            available_bases=available_bases,
            total_points=int(adata.n_obs),
            returned_points=0,
            is_sampled=False,
            points=[],
        )

    total_points = int(adata.n_obs)
    if total_points > max_points:
        step = max(total_points // max_points, 1)
        indices = list(range(0, total_points, step))[:max_points]
    else:
        indices = list(range(total_points))

    coords = adata.obsm[obsm_key][indices, :2]
    obs = adata.obs.iloc[indices].copy()
    points = []
    for output_index, (obs_index, row) in enumerate(obs.iterrows()):
        metadata = {
            key: jsonable(value)
            for key, value in row.to_dict().items()
            if key in EMBEDDING_METADATA_KEYS
        }
        label = row.get("cell_type") or row.get("cluster") or row.get("sample_id")
        points.append(
            EmbeddingPoint(
                obs_index=indices[output_index],
                sample_id=None if str(row.get("sample_id")) == "nan" else str(row.get("sample_id")),
                x=float(coords[output_index][0]),
                y=float(coords[output_index][1]),
                label=jsonable(label),
                metadata=metadata,
            )
        )

    return EmbeddingResponse(
        dataset_id=dataset_id,
        basis=requested_basis,
        available_bases=available_bases,
        total_points=total_points,
        returned_points=len(points),
        is_sampled=total_points > len(points),
        points=points,
    )


@app.get("/cells", response_model=list[CellResult])
def query_cells(
    cell_type: str | None = Query(default=None),
    disease: str | None = Query(default=None),
    tissue: str | None = Query(default=None),
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
) -> list[CellResult]:
    stmt = select(Cell).outerjoin(Sample)
    if cell_type:
        stmt = stmt.where(Cell.cell_type.ilike(f"%{cell_type}%"))
    if disease:
        stmt = stmt.where(Sample.disease.ilike(f"%{disease}%"))
    if tissue:
        stmt = stmt.where(Sample.tissue.ilike(f"%{tissue}%"))
    if dataset_id:
        stmt = stmt.where(Cell.dataset_id == dataset_id)

    rows = db.execute(stmt.order_by(Cell.dataset_id, Cell.obs_index).limit(limit)).scalars().all()
    return [
        CellResult(
            dataset_id=row.dataset_id,
            obs_index=row.obs_index,
            sample_id=row.sample_id,
            cell_type=row.cell_type,
            cluster=row.cluster,
        )
        for row in rows
    ]


@app.post("/cells/data", response_model=CellDataResponse)
def get_cell_data(payload: CellDataRequest, db: Session = Depends(get_db)) -> CellDataResponse:
    dataset = db.get(Dataset, payload.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not payload.indices:
        raise HTTPException(status_code=400, detail="At least one cell index is required")

    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Source h5ad file not found")

    adata = sc.read_h5ad(file_path)
    max_index = adata.n_obs - 1
    invalid = [index for index in payload.indices if index < 0 or index > max_index]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid indices: {invalid}")

    subset = adata[payload.indices, :]
    matrix = subset.X.toarray() if hasattr(subset.X, "toarray") else subset.X
    expression = [[float(value) for value in row] for row in matrix.tolist()]
    obs_records = subset.obs.reset_index(drop=True).to_dict(orient="records")

    return CellDataResponse(
        dataset_id=payload.dataset_id,
        indices=payload.indices,
        genes=[str(gene) for gene in subset.var_names.tolist()],
        expression=expression,
        obs=obs_records,
    )


@app.get("/metadata/options")
def metadata_options(db: Session = Depends(get_db)) -> dict[str, list[str]]:
    disease_values = sorted(
        value
        for value in db.execute(select(distinct(Sample.disease)).where(Sample.disease.is_not(None))).scalars().all()
        if value
    )
    tissue_values = sorted(
        value
        for value in db.execute(select(distinct(Sample.tissue)).where(Sample.tissue.is_not(None))).scalars().all()
        if value
    )
    omics_values = sorted(
        value
        for value in db.execute(
            select(distinct(Dataset.omics_type)).where(Dataset.omics_type.is_not(None))
        ).scalars().all()
        if value
    )
    return {"diseases": disease_values, "tissues": tissue_values, "omics_types": omics_values}
