# Data Directory

This repository intentionally does not commit downloaded or processed H5AD/count files.

Expected local layout:

- `raw/single_cell/`: CELLxGENE source H5AD downloads
- `raw/bulk/`: recount3 raw count matrices and sample metadata
- `processed/h5ad/`: normalized H5AD files ingested by the app
- `manifests/`: generated CSV manifests and preprocessing reports
- `backups/`: local backups made before resetting demo data

Use the scripts documented in the root `README.md` to regenerate data on a new machine.

