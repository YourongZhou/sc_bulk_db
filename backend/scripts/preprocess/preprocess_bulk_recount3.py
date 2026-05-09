import argparse
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


def read_counts(path: Path) -> pd.DataFrame:
    counts = pd.read_csv(path, sep="\t", index_col=0)
    counts = counts.apply(pd.to_numeric, errors="coerce").fillna(0)
    return counts


def read_metadata(path: Path, sample_ids: list[str]) -> pd.DataFrame:
    if path.exists():
        metadata = pd.read_csv(path, sep="\t", index_col=0)
    else:
        metadata = pd.DataFrame(index=sample_ids)
    metadata.index = metadata.index.astype(str)
    missing = [sample_id for sample_id in sample_ids if sample_id not in metadata.index]
    if missing:
        metadata = pd.concat([metadata, pd.DataFrame(index=missing)], axis=0)
    return metadata.loc[sample_ids].copy()


def first_existing(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def normalize_metadata(metadata: pd.DataFrame, project_id: str) -> pd.DataFrame:
    metadata = metadata.copy()
    metadata["sample_id"] = metadata.index.astype(str)
    defaults = {
        "cell_type": "Bulk profile",
        "cluster": "bulk",
        "disease": "unknown",
        "tissue": "blood",
        "condition": "unknown",
    }
    sources = {
        "disease": ["disease", "health_status", "sra_attribute.disease", "phenotype"],
        "tissue": ["tissue", "tissue_general", "sra_attribute.tissue", "body_site"],
        "condition": ["condition", "status", "treatment", "sra_attribute.condition"],
    }
    for column, value in defaults.items():
        if column in {"disease", "tissue", "condition"}:
            source = first_existing(metadata, sources[column])
            metadata[column] = metadata[source].astype(str) if source else value
        else:
            metadata[column] = value
        metadata[column] = metadata[column].replace({"nan": "unknown", "None": "unknown", "": "unknown"})
    metadata["recount3_project"] = project_id
    return metadata


def log_cpm(counts: pd.DataFrame, min_count: int, min_samples: int) -> pd.DataFrame:
    keep = (counts >= min_count).sum(axis=1) >= min_samples
    filtered = counts.loc[keep]
    if filtered.empty:
        filtered = counts
    library_sizes = filtered.sum(axis=0).replace(0, np.nan)
    cpm = filtered.divide(library_sizes, axis=1) * 1_000_000
    return np.log2(cpm.fillna(0) + 1)


def build_pca(matrix: pd.DataFrame) -> np.ndarray:
    sample_matrix = matrix.T.to_numpy(dtype=np.float32)
    if sample_matrix.shape[0] < 2 or sample_matrix.shape[1] < 2:
        return np.zeros((sample_matrix.shape[0], 2), dtype=np.float32)
    n_components = min(2, sample_matrix.shape[0], sample_matrix.shape[1])
    coords = PCA(n_components=n_components).fit_transform(sample_matrix)
    if coords.shape[1] == 1:
        coords = np.column_stack([coords[:, 0], np.zeros(coords.shape[0])])
    return coords.astype(np.float32)


def preprocess_project(project_dir: Path, output_dir: Path, min_count: int, min_samples: int) -> dict:
    project_id = project_dir.name
    counts_path = project_dir / "gene_counts.tsv.gz"
    metadata_path = project_dir / "sample_metadata.tsv.gz"
    counts = read_counts(counts_path)
    matrix = log_cpm(counts, min_count, min_samples)
    metadata = normalize_metadata(read_metadata(metadata_path, list(matrix.columns)), project_id)

    adata = ad.AnnData(
        X=matrix.T.to_numpy(dtype=np.float32),
        obs=metadata,
        var=pd.DataFrame(index=matrix.index.astype(str)),
    )
    adata.obsm["X_pca"] = build_pca(matrix)
    adata.uns["dataset_metadata"] = {
        "dataset_id": project_id,
        "title": project_id.replace("_", " ").replace("-", " ").title(),
        "description": f"recount3 bulk RNA-seq gene counts processed from {project_id}",
        "omics_type": "bulk RNA-seq",
        "species": "human",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{project_id}.h5ad"
    adata.write_h5ad(output_path, compression="gzip")
    return {
        "dataset_id": project_id,
        "source_dir": str(project_dir),
        "processed_path": str(output_path),
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "has_pca": "X_pca" in adata.obsm,
        "error": "",
    }


def selected_project_dirs(manifest_path: Path | None, raw_dir: Path) -> list[Path]:
    if manifest_path and manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        rows = manifest[manifest.get("selected", True).astype(bool)]
        if "downloaded" in rows.columns:
            rows = rows[rows["downloaded"].astype(bool)]
        return [Path(path) for path in rows["local_dir"].dropna().astype(str)]
    return sorted(path for path in raw_dir.iterdir() if path.is_dir())


def update_manifest(manifest_path: Path, records: list[dict]) -> None:
    if not manifest_path.exists():
        return
    manifest = pd.read_csv(manifest_path)
    if "processed_path" not in manifest.columns:
        manifest["processed_path"] = ""
    manifest["error"] = manifest.get("error", "").fillna("").astype(str)
    manifest["processed_path"] = manifest["processed_path"].fillna("").astype(str)
    record_by_source = {record["source_dir"]: record for record in records}
    for index, row in manifest.iterrows():
        record = record_by_source.get(str(row.get("local_dir", "")))
        if not record:
            continue
        manifest.loc[index, "preprocessed"] = not bool(record.get("error"))
        manifest.loc[index, "processed_path"] = record.get("processed_path", "")
        manifest.loc[index, "error"] = record.get("error", "")
    manifest.to_csv(manifest_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert recount3 bulk count matrices to ingestible H5AD files.")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/bulk_manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bulk"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/h5ad"))
    parser.add_argument("--report", type=Path, default=Path("data/manifests/bulk_preprocess_report.csv"))
    parser.add_argument("--min-count", type=int, default=10)
    parser.add_argument("--min-samples", type=int, default=2)
    args = parser.parse_args()

    records = []
    for project_dir in selected_project_dirs(args.manifest, args.raw_dir):
        try:
            records.append(preprocess_project(project_dir, args.output_dir, args.min_count, args.min_samples))
        except Exception as exc:
            records.append(
                {
                    "dataset_id": project_dir.name,
                    "source_dir": str(project_dir),
                    "processed_path": "",
                    "n_obs": 0,
                    "n_vars": 0,
                    "has_pca": False,
                    "error": str(exc),
                }
            )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(args.report, index=False)
    update_manifest(args.manifest, records)
    print(f"Wrote preprocess report to {args.report}")


if __name__ == "__main__":
    main()
