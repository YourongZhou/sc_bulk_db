from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()
INIT_DB_LOCK_KEY = 20260510

POPULATION_GROUP_SEED = (
    (1, "plateau_high_cold", "高原高寒环境人群", 3, 6),
    (2, "tropical_heat_tolerant", "热带环境耐热人群", 3, 6),
    (3, "plain_ams_patient", "平原环境人群高原反应患者", 2, 2),
    (4, "plain_low_altitude", "平原环境低海拔人群", 10, 10),
)

GROUP_MODALITY_COUNTS_VIEW_SQL = """
CREATE OR REPLACE VIEW vw_group_modality_counts AS
SELECT
    pg.group_id,
    pg.group_code,
    pg.group_name,
    COUNT(DISTINCT CASE WHEN sda.modality = 'single_cell_h5ad' AND sda.is_active THEN s.sample_id END) AS single_cell_sample_count,
    COUNT(DISTINCT CASE WHEN sda.modality = 'bulk' AND sda.is_active THEN s.sample_id END) AS bulk_sample_count,
    COUNT(DISTINCT CASE WHEN sda.modality = 'fastq' AND sda.is_active THEN s.sample_id END) AS fastq_sample_count
FROM population_groups pg
LEFT JOIN samples s ON s.group_id = pg.group_id
LEFT JOIN sample_data_assets sda ON sda.sample_id = s.sample_id
GROUP BY pg.group_id, pg.group_code, pg.group_name
"""

GROUP_QUOTA_STATUS_VIEW_SQL = """
CREATE OR REPLACE VIEW vw_group_quota_status AS
SELECT
    pg.group_id,
    pg.group_code,
    pg.group_name,
    counts.single_cell_sample_count,
    counts.bulk_sample_count,
    counts.fastq_sample_count,
    pg.min_single_cell_samples,
    pg.min_bulk_samples,
    counts.single_cell_sample_count >= pg.min_single_cell_samples AS single_cell_ok,
    counts.bulk_sample_count >= pg.min_bulk_samples AS bulk_ok
FROM population_groups pg
LEFT JOIN vw_group_modality_counts counts ON counts.group_id = pg.group_id
"""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import PopulationGroup, Sample, SampleDataAsset, SingleCellCell  # noqa: F401

    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": INIT_DB_LOCK_KEY})
        try:
            Base.metadata.create_all(bind=connection)
            for group_id, group_code, group_name, min_single_cell, min_bulk in POPULATION_GROUP_SEED:
                connection.execute(
                    text(
                        """
                        INSERT INTO population_groups (
                            group_id,
                            group_code,
                            group_name,
                            min_single_cell_samples,
                            min_bulk_samples
                        )
                        VALUES (
                            :group_id,
                            :group_code,
                            :group_name,
                            :min_single_cell_samples,
                            :min_bulk_samples
                        )
                        ON CONFLICT (group_code) DO UPDATE
                        SET
                            group_name = EXCLUDED.group_name,
                            min_single_cell_samples = EXCLUDED.min_single_cell_samples,
                            min_bulk_samples = EXCLUDED.min_bulk_samples
                        """
                    ),
                    {
                        "group_id": group_id,
                        "group_code": group_code,
                        "group_name": group_name,
                        "min_single_cell_samples": min_single_cell,
                        "min_bulk_samples": min_bulk,
                    },
                )
            connection.execute(text(GROUP_MODALITY_COUNTS_VIEW_SQL))
            connection.execute(text(GROUP_QUOTA_STATUS_VIEW_SQL))
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": INIT_DB_LOCK_KEY})
