CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    omics_type TEXT NOT NULL,
    species TEXT NOT NULL,
    file_path TEXT NOT NULL,
    n_cells INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    sample_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    disease TEXT,
    tissue TEXT,
    condition TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS cells (
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    obs_index INTEGER NOT NULL,
    sample_id TEXT REFERENCES samples(sample_id),
    cell_type TEXT,
    cluster TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (dataset_id, obs_index)
);
