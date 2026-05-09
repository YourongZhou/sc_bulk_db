from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    omics_type: Mapped[str] = mapped_column(Text, nullable=False)
    species: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    n_cells: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    samples: Mapped[list["Sample"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    cells: Mapped[list["Cell"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class Sample(Base):
    __tablename__ = "samples"

    sample_id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    disease: Mapped[str | None] = mapped_column(Text, nullable=True)
    tissue: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    dataset: Mapped["Dataset"] = relationship(back_populates="samples")
    cells: Mapped[list["Cell"]] = relationship(back_populates="sample")


class Cell(Base):
    __tablename__ = "cells"
    __table_args__ = (PrimaryKeyConstraint("dataset_id", "obs_index"),)

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    obs_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_id: Mapped[str | None] = mapped_column(ForeignKey("samples.sample_id"), nullable=True)
    cell_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    dataset: Mapped["Dataset"] = relationship(back_populates="cells")
    sample: Mapped["Sample"] = relationship(back_populates="cells")
