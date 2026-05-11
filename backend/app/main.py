import mimetypes
from pathlib import Path

import scanpy as sc
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db, init_db
from app.models import PopulationGroup, Sample, SampleDataAsset, SingleCellCell
from app.schemas import (
    EmbeddingPoint,
    EmbeddingResponse,
    PopulationGroupInfo,
    PopulationGroupQuotaStatus,
    SampleAsset,
    SampleDetail,
    SampleSummary,
    SingleCellDataRequest,
    SingleCellDataResponse,
    SingleCellResult,
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


def jsonable(value):
    if value is None or str(value) == "nan":
        return None
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def resolve_data_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "data":
        return Path(settings.data_dir).parent.joinpath(*parts[1:])
    return path.resolve()


def serialize_group(group: PopulationGroup) -> PopulationGroupInfo:
    return PopulationGroupInfo(group_id=group.group_id, group_code=group.group_code, group_name=group.group_name)


def modality_for_data_type(data_type: str | None) -> str | None:
    mapping = {
        "fastq": "fastq",
        "rna_seq": "single_cell_h5ad",
        "bulk": "bulk",
    }
    if data_type is None:
        return None
    resolved = mapping.get(data_type)
    if not resolved:
        raise HTTPException(status_code=400, detail="Unsupported data_type. Use one of: fastq, rna_seq, bulk")
    return resolved


def collect_single_cell_counts(db: Session, asset_ids: list[int]) -> dict[int, int]:
    if not asset_ids:
        return {}
    rows = db.execute(
        select(SingleCellCell.asset_id, func.count(SingleCellCell.obs_index))
        .where(SingleCellCell.asset_id.in_(asset_ids))
        .group_by(SingleCellCell.asset_id)
    ).all()
    return {asset_id: count for asset_id, count in rows}


def serialize_asset(sample_id: str, asset: SampleDataAsset) -> SampleAsset:
    return SampleAsset(
        asset_id=asset.asset_id,
        modality=asset.modality,
        file_format=asset.file_format,
        file_name=asset.file_name,
        size_bytes=asset.size_bytes,
        source_url=asset.source_url,
        is_active=asset.is_active,
        download_url=f"/samples/{sample_id}/assets/{asset.asset_id}/download",
        metadata=asset.metadata_json,
    )


def serialize_sample(sample: Sample, cell_count_map: dict[int, int]) -> SampleSummary:
    assets_by_modality = {asset.modality: asset for asset in sample.assets if asset.is_active}
    single_cell_asset = assets_by_modality.get("single_cell_h5ad")
    return SampleSummary(
        sample_id=sample.sample_id,
        sample_code=sample.sample_code,
        group=serialize_group(sample.group),
        subject_id=sample.subject_id,
        study_id=sample.study_id,
        title=sample.title,
        description=sample.description,
        species=sample.species,
        tissue=sample.tissue,
        condition=sample.condition,
        collection_site=sample.collection_site,
        created_at=sample.created_at,
        has_fastq="fastq" in assets_by_modality,
        has_single_cell=single_cell_asset is not None,
        has_bulk="bulk" in assets_by_modality,
        modalities=sorted(assets_by_modality.keys()),
        single_cell_asset_id=single_cell_asset.asset_id if single_cell_asset else None,
        single_cell_cell_count=cell_count_map.get(single_cell_asset.asset_id, 0) if single_cell_asset else 0,
        metadata=sample.metadata_json,
    )


def get_single_cell_asset(
    db: Session,
    *,
    sample_id: str | None = None,
    asset_id: int | None = None,
) -> tuple[Sample, SampleDataAsset]:
    if asset_id is None and sample_id is None:
        raise HTTPException(status_code=400, detail="sample_id or asset_id is required")

    asset: SampleDataAsset | None = None
    if asset_id is not None:
        asset = db.get(SampleDataAsset, asset_id)
        if not asset or not asset.is_active:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.modality != "single_cell_h5ad":
            raise HTTPException(status_code=400, detail="Asset is not a single-cell h5ad asset")
        sample = db.get(Sample, asset.sample_id)
        if not sample:
            raise HTTPException(status_code=404, detail="Sample not found")
        return sample, asset

    sample = db.execute(
        select(Sample)
        .where(Sample.sample_id == sample_id)
        .options(selectinload(Sample.group), selectinload(Sample.assets))
    ).scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    for candidate in sample.assets:
        if candidate.is_active and candidate.modality == "single_cell_h5ad":
            return sample, candidate
    raise HTTPException(status_code=404, detail="Single-cell h5ad asset not found for sample")


@app.get("/samples", response_model=list[SampleSummary])
def list_samples(
    group_code: str | None = Query(default=None),
    tissue: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    species: str | None = Query(default=None),
    data_type: str | None = Query(default=None),
    has_fastq: bool | None = Query(default=None),
    has_single_cell: bool | None = Query(default=None),
    has_bulk: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SampleSummary]:
    stmt = select(Sample).join(PopulationGroup).options(selectinload(Sample.group), selectinload(Sample.assets))
    if group_code:
        stmt = stmt.where(PopulationGroup.group_code == group_code)
    if tissue:
        stmt = stmt.where(Sample.tissue.ilike(f"%{tissue}%"))
    if condition:
        stmt = stmt.where(Sample.condition.ilike(f"%{condition}%"))
    if species:
        stmt = stmt.where(Sample.species.ilike(f"%{species}%"))
    if data_type:
        modality = modality_for_data_type(data_type)
        data_type_exists = (
            select(SampleDataAsset.asset_id)
            .where(
                SampleDataAsset.sample_id == Sample.sample_id,
                SampleDataAsset.modality == modality,
                SampleDataAsset.is_active.is_(True),
            )
            .exists()
        )
        stmt = stmt.where(data_type_exists)

    if has_fastq is not None:
        fastq_exists = (
            select(SampleDataAsset.asset_id)
            .where(
                SampleDataAsset.sample_id == Sample.sample_id,
                SampleDataAsset.modality == "fastq",
                SampleDataAsset.is_active.is_(True),
            )
            .exists()
        )
        stmt = stmt.where(fastq_exists if has_fastq else ~fastq_exists)
    if has_single_cell is not None:
        sc_exists = (
            select(SampleDataAsset.asset_id)
            .where(
                SampleDataAsset.sample_id == Sample.sample_id,
                SampleDataAsset.modality == "single_cell_h5ad",
                SampleDataAsset.is_active.is_(True),
            )
            .exists()
        )
        stmt = stmt.where(sc_exists if has_single_cell else ~sc_exists)
    if has_bulk is not None:
        bulk_exists = (
            select(SampleDataAsset.asset_id)
            .where(
                SampleDataAsset.sample_id == Sample.sample_id,
                SampleDataAsset.modality == "bulk",
                SampleDataAsset.is_active.is_(True),
            )
            .exists()
        )
        stmt = stmt.where(bulk_exists if has_bulk else ~bulk_exists)

    samples = db.execute(stmt.order_by(Sample.created_at.desc(), Sample.sample_id)).scalars().unique().all()
    asset_ids = [asset.asset_id for sample in samples for asset in sample.assets if asset.modality == "single_cell_h5ad"]
    cell_count_map = collect_single_cell_counts(db, asset_ids)
    return [serialize_sample(sample, cell_count_map) for sample in samples]


@app.get("/samples/{sample_id}", response_model=SampleDetail)
def get_sample(sample_id: str, db: Session = Depends(get_db)) -> SampleDetail:
    sample = db.execute(
        select(Sample)
        .where(Sample.sample_id == sample_id)
        .options(selectinload(Sample.group), selectinload(Sample.assets))
    ).scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    asset_ids = [asset.asset_id for asset in sample.assets if asset.modality == "single_cell_h5ad"]
    cell_count_map = collect_single_cell_counts(db, asset_ids)
    summary = serialize_sample(sample, cell_count_map)
    return SampleDetail(**summary.model_dump(), assets=[serialize_asset(sample.sample_id, asset) for asset in sample.assets])


@app.get("/samples/{sample_id}/assets/{asset_id}/download")
def download_sample_asset(sample_id: str, asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(SampleDataAsset, asset_id)
    if not asset or asset.sample_id != sample_id or not asset.is_active:
        raise HTTPException(status_code=404, detail="Asset not found")

    file_path = Path(asset.file_path)
    if not file_path.exists() or not file_path.is_file():
        resolved_path = resolve_data_path(asset.file_path)
        if not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=404, detail="Download file not found")
        file_path = resolved_path

    media_type = mimetypes.guess_type(asset.file_name)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type, filename=asset.file_name)


@app.get("/samples/{sample_id}/embedding", response_model=EmbeddingResponse)
def get_sample_embedding(
    sample_id: str,
    basis: str | None = Query(default=None, pattern="^(umap|pca)$"),
    max_points: int = Query(default=5000, ge=100, le=50000),
    db: Session = Depends(get_db),
) -> EmbeddingResponse:
    sample, asset = get_single_cell_asset(db, sample_id=sample_id)
    requested_basis = basis or "umap"
    file_path = resolve_data_path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Source h5ad file not found")

    adata = sc.read_h5ad(file_path, backed="r")
    available_bases = sorted(key.replace("X_", "") for key in adata.obsm.keys() if key.startswith("X_"))
    obsm_key = f"X_{requested_basis}"
    if obsm_key not in adata.obsm:
        return EmbeddingResponse(
            sample_id=sample.sample_id,
            asset_id=asset.asset_id,
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
                sample_id=sample.sample_id,
                x=float(coords[output_index][0]),
                y=float(coords[output_index][1]),
                label=jsonable(label),
                metadata=metadata,
            )
        )

    return EmbeddingResponse(
        sample_id=sample.sample_id,
        asset_id=asset.asset_id,
        basis=requested_basis,
        available_bases=available_bases,
        total_points=total_points,
        returned_points=len(points),
        is_sampled=total_points > len(points),
        points=points,
    )


@app.get("/groups/quota-status", response_model=list[PopulationGroupQuotaStatus])
def group_quota_status(db: Session = Depends(get_db)) -> list[PopulationGroupQuotaStatus]:
    rows = db.execute(
        text(
            """
            SELECT
                group_id,
                group_code,
                group_name,
                COALESCE(single_cell_sample_count, 0) AS single_cell_sample_count,
                COALESCE(bulk_sample_count, 0) AS bulk_sample_count,
                COALESCE(fastq_sample_count, 0) AS fastq_sample_count,
                min_single_cell_samples,
                min_bulk_samples,
                COALESCE(single_cell_ok, false) AS single_cell_ok,
                COALESCE(bulk_ok, false) AS bulk_ok
            FROM vw_group_quota_status
            ORDER BY group_id
            """
        )
    ).mappings()
    return [PopulationGroupQuotaStatus(**dict(row)) for row in rows]


@app.get("/single-cell/cells", response_model=list[SingleCellResult])
def query_single_cell_cells(
    cell_type: str | None = Query(default=None),
    tissue: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    group_code: str | None = Query(default=None),
    sample_id: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
) -> list[SingleCellResult]:
    stmt = (
        select(SingleCellCell, Sample, PopulationGroup)
        .join(SampleDataAsset, SingleCellCell.asset_id == SampleDataAsset.asset_id)
        .join(Sample, SampleDataAsset.sample_id == Sample.sample_id)
        .join(PopulationGroup, Sample.group_id == PopulationGroup.group_id)
        .where(SampleDataAsset.modality == "single_cell_h5ad", SampleDataAsset.is_active.is_(True))
    )
    if cell_type:
        stmt = stmt.where(SingleCellCell.cell_type.ilike(f"%{cell_type}%"))
    if tissue:
        stmt = stmt.where(Sample.tissue.ilike(f"%{tissue}%"))
    if condition:
        stmt = stmt.where(Sample.condition.ilike(f"%{condition}%"))
    if group_code:
        stmt = stmt.where(PopulationGroup.group_code == group_code)
    if sample_id:
        stmt = stmt.where(Sample.sample_id == sample_id)

    rows = db.execute(stmt.order_by(Sample.sample_code, SingleCellCell.obs_index).limit(limit)).all()
    return [
        SingleCellResult(
            asset_id=cell.asset_id,
            sample_id=sample.sample_id,
            sample_code=sample.sample_code,
            group_code=group.group_code,
            obs_index=cell.obs_index,
            sample_barcode=cell.sample_barcode,
            cell_type=cell.cell_type,
            cluster=cell.cluster,
        )
        for cell, sample, group in rows
    ]


@app.post("/single-cell/data", response_model=SingleCellDataResponse)
def get_single_cell_data(payload: SingleCellDataRequest, db: Session = Depends(get_db)) -> SingleCellDataResponse:
    sample, asset = get_single_cell_asset(db, sample_id=payload.sample_id, asset_id=payload.asset_id)
    if not payload.indices:
        raise HTTPException(status_code=400, detail="At least one cell index is required")

    file_path = resolve_data_path(asset.file_path)
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

    return SingleCellDataResponse(
        asset_id=asset.asset_id,
        sample_id=sample.sample_id,
        indices=payload.indices,
        genes=[str(gene) for gene in subset.var_names.tolist()],
        expression=expression,
        obs=obs_records,
    )


@app.get("/metadata/options")
def metadata_options(db: Session = Depends(get_db)) -> dict[str, list[str]]:
    tissue_values = sorted(
        value
        for value in db.execute(select(distinct(Sample.tissue)).where(Sample.tissue.is_not(None))).scalars().all()
        if value
    )
    condition_values = sorted(
        value
        for value in db.execute(select(distinct(Sample.condition)).where(Sample.condition.is_not(None))).scalars().all()
        if value
    )
    species_values = sorted(
        value
        for value in db.execute(select(distinct(Sample.species)).where(Sample.species.is_not(None))).scalars().all()
        if value
    )
    groups = db.execute(select(PopulationGroup).order_by(PopulationGroup.group_id)).scalars().all()
    return {
        "group_codes": [group.group_code for group in groups],
        "group_names": [group.group_name for group in groups],
        "data_types": ["fastq", "rna_seq", "bulk"],
        "tissues": tissue_values,
        "conditions": condition_values,
        "species": species_values,
    }
