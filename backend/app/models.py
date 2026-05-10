from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, PrimaryKeyConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


GROUP_CODES = (
    "plateau_high_cold",
    "tropical_heat_tolerant",
    "plain_ams_patient",
    "plain_low_altitude",
)
ASSET_MODALITIES = ("fastq", "single_cell_h5ad", "bulk")
ASSET_FILE_FORMATS = ("fastq.gz", "h5ad", "csv", "tsv", "txt")


class PopulationGroup(Base):
    __tablename__ = "population_groups"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    group_name: Mapped[str] = mapped_column(Text, nullable=False)
    min_single_cell_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    min_bulk_samples: Mapped[int] = mapped_column(Integer, nullable=False)

    samples: Mapped[list["Sample"]] = relationship(back_populates="group")


class Sample(Base):
    __tablename__ = "samples"

    sample_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sample_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("population_groups.group_id"), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    study_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    species: Mapped[str | None] = mapped_column(Text, nullable=True, default="human")
    tissue: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    collection_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    group: Mapped["PopulationGroup"] = relationship(back_populates="samples")
    assets: Mapped[list["SampleDataAsset"]] = relationship(
        back_populates="sample",
        cascade="all, delete-orphan",
        order_by="SampleDataAsset.asset_id",
    )


class SampleDataAsset(Base):
    __tablename__ = "sample_data_assets"
    __table_args__ = (
        UniqueConstraint("sample_id", "modality"),
        CheckConstraint(f"modality IN {ASSET_MODALITIES}", name="sample_data_assets_modality_check"),
        CheckConstraint(f"file_format IN {ASSET_FILE_FORMATS}", name="sample_data_assets_file_format_check"),
    )

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[str] = mapped_column(ForeignKey("samples.sample_id", ondelete="CASCADE"), nullable=False)
    modality: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sample: Mapped["Sample"] = relationship(back_populates="assets")
    cells: Mapped[list["SingleCellCell"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="SingleCellCell.obs_index",
    )


class SingleCellCell(Base):
    __tablename__ = "single_cell_cells"
    __table_args__ = (PrimaryKeyConstraint("asset_id", "obs_index"),)

    asset_id: Mapped[int] = mapped_column(ForeignKey("sample_data_assets.asset_id", ondelete="CASCADE"), nullable=False)
    obs_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    asset: Mapped["SampleDataAsset"] = relationship(back_populates="cells")
