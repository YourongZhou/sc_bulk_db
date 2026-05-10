from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PopulationGroupInfo(BaseModel):
    group_id: int
    group_code: str
    group_name: str


class PopulationGroupQuotaStatus(PopulationGroupInfo):
    single_cell_sample_count: int
    bulk_sample_count: int
    fastq_sample_count: int
    min_single_cell_samples: int
    min_bulk_samples: int
    single_cell_ok: bool
    bulk_ok: bool


class SampleAsset(BaseModel):
    asset_id: int
    modality: str
    file_format: str
    file_name: str
    size_bytes: int | None
    source_url: str | None
    is_active: bool
    download_url: str
    metadata: dict[str, Any]


class SampleSummary(BaseModel):
    sample_id: str
    sample_code: str
    group: PopulationGroupInfo
    subject_id: str | None
    study_id: str | None
    title: str | None
    description: str | None
    species: str | None
    tissue: str | None
    condition: str | None
    collection_site: str | None
    created_at: datetime
    has_fastq: bool
    has_single_cell: bool
    has_bulk: bool
    modalities: list[str]
    single_cell_asset_id: int | None
    single_cell_cell_count: int
    metadata: dict[str, Any]


class SampleDetail(SampleSummary):
    assets: list[SampleAsset]


class SingleCellResult(BaseModel):
    asset_id: int
    sample_id: str
    sample_code: str
    group_code: str
    obs_index: int
    sample_barcode: str | None
    cell_type: str | None
    cluster: str | None


class SingleCellDataRequest(BaseModel):
    sample_id: str | None = None
    asset_id: int | None = None
    indices: list[int] = Field(default_factory=list)


class SingleCellDataResponse(BaseModel):
    asset_id: int
    sample_id: str
    indices: list[int]
    genes: list[str]
    expression: list[list[float]]
    obs: list[dict[str, Any]]


class EmbeddingPoint(BaseModel):
    obs_index: int
    sample_id: str | None
    x: float
    y: float
    label: str | None
    metadata: dict[str, Any]


class EmbeddingResponse(BaseModel):
    sample_id: str
    asset_id: int
    basis: str
    available_bases: list[str]
    total_points: int
    returned_points: int
    is_sampled: bool
    points: list[EmbeddingPoint]
