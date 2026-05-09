from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    title: str
    description: str
    omics_type: str
    species: str
    n_cells: int
    created_at: datetime
    disease_values: list[str]
    tissue_values: list[str]
    condition_values: list[str]


class DatasetDetail(DatasetSummary):
    file_path: str
    sample_count: int
    sample_preview: list[dict[str, Any]]


class CellResult(BaseModel):
    dataset_id: str
    obs_index: int
    sample_id: str | None
    cell_type: str | None
    cluster: str | None


class CellDataRequest(BaseModel):
    dataset_id: str
    indices: list[int] = Field(default_factory=list)


class CellDataResponse(BaseModel):
    dataset_id: str
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
    dataset_id: str
    basis: str
    available_bases: list[str]
    total_points: int
    returned_points: int
    is_sampled: bool
    points: list[EmbeddingPoint]
