import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc


REQUIRED_OBS = ["sample_id", "cell_type", "cluster", "disease", "tissue", "condition"]


def first_existing(obs: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in obs.columns:
            return column
    return None


def normalize_obs(adata, dataset_id: str) -> list[str]:
    obs = adata.obs.copy()
    notes: list[str] = []

    source_map = {
        "sample_id": ["sample_id", "sample", "donor_id", "author_sample_id", "batch", "library_id"],
        "cell_type": ["cell_type", "cell_type_alias", "celltype", "annotation", "cell_type_ontology_term_id"],
        "cluster": ["cluster", "leiden", "louvain", "seurat_clusters"],
        "disease": ["disease", "disease_ontology_term_id"],
        "tissue": ["tissue", "tissue_general", "tissue_ontology_term_id"],
        "condition": ["condition", "disease", "development_stage", "sex"],
    }

    for required, candidates in source_map.items():
        source = first_existing(obs, candidates)
        if source:
            obs[required] = obs[source].astype(str).replace({"nan": "unknown", "None": "unknown"})
            if source != required:
                notes.append(f"{required} copied from {source}")
        else:
            if required == "sample_id":
                obs[required] = f"{dataset_id}_sample"
            elif required == "cell_type":
                obs[required] = "Unknown cell"
            elif required == "cluster":
                obs[required] = "unclustered"
            elif required == "disease":
                obs[required] = "unknown"
            elif required == "tissue":
                obs[required] = "blood"
            else:
                obs[required] = "unknown"
            notes.append(f"{required} filled with default")

    adata.obs = obs
    return notes


def ensure_umap(adata, max_cells_for_umap: int) -> str:
    if "X_umap" in adata.obsm and adata.obsm["X_umap"].shape[1] >= 2:
        return "existing"
    if adata.n_obs < 3:
        adata.obsm["X_umap"] = np.zeros((adata.n_obs, 2), dtype=np.float32)
        return "zeros_small_dataset"
    if adata.n_obs > max_cells_for_umap:
        if "X_pca" in adata.obsm and adata.obsm["X_pca"].shape[1] >= 2:
            adata.obsm["X_umap"] = np.asarray(adata.obsm["X_pca"][:, :2], dtype=np.float32)
            return "pca_fallback_large_dataset"
        rng = np.random.default_rng(abs(hash("umap:" + str(adata.n_obs))) % (2**32))
        adata.obsm["X_umap"] = rng.normal(size=(adata.n_obs, 2)).astype(np.float32)
        return "random_fallback_large_dataset"

    work = adata.copy()
    try:
        if work.n_vars > 2_000:
            sc.pp.highly_variable_genes(work, n_top_genes=2_000, flavor="cell_ranger", subset=True)
        sc.pp.normalize_total(work, target_sum=1e4)
        sc.pp.log1p(work)
        sc.pp.pca(work, n_comps=min(50, work.n_obs - 1, work.n_vars - 1))
        sc.pp.neighbors(work, n_neighbors=min(15, max(2, work.n_obs - 1)))
        sc.tl.umap(work)
        adata.obsm["X_umap"] = np.asarray(work.obsm["X_umap"], dtype=np.float32)
        return "computed_scanpy"
    except Exception:
        if "X_pca" in adata.obsm and adata.obsm["X_pca"].shape[1] >= 2:
            adata.obsm["X_umap"] = np.asarray(adata.obsm["X_pca"][:, :2], dtype=np.float32)
            return "pca_fallback_after_error"
        rng = np.random.default_rng(abs(hash("umap-fallback:" + str(adata.n_obs))) % (2**32))
        adata.obsm["X_umap"] = rng.normal(size=(adata.n_obs, 2)).astype(np.float32)
        return "random_fallback_after_error"


def dataset_metadata(adata, dataset_id: str, source_path: Path) -> dict[str, str]:
    existing = dict(adata.uns.get("dataset_metadata", {}))
    return {
        "dataset_id": existing.get("dataset_id", dataset_id),
        "title": existing.get("title", dataset_id.replace("_", " ").title()),
        "description": existing.get("description", f"CELLxGENE source H5AD processed from {source_path.name}"),
        "omics_type": existing.get("omics_type", "scRNA-seq"),
        "species": existing.get("species", "human"),
    }


def preprocess_file(source_path: Path, output_dir: Path, max_cells_for_umap: int) -> dict:
    dataset_id = source_path.stem
    adata = sc.read_h5ad(source_path)
    notes = normalize_obs(adata, dataset_id)
    umap_status = ensure_umap(adata, max_cells_for_umap)
    adata.uns["dataset_metadata"] = dataset_metadata(adata, dataset_id, source_path)
    adata.uns["preprocessing_notes"] = notes + [f"umap_status={umap_status}"]

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{adata.uns['dataset_metadata']['dataset_id']}.h5ad"
    adata.write_h5ad(output_path, compression="gzip")
    return {
        "dataset_id": adata.uns["dataset_metadata"]["dataset_id"],
        "source_path": str(source_path),
        "processed_path": str(output_path),
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "has_umap": "X_umap" in adata.obsm,
        "umap_status": umap_status,
        "error": "",
    }


def selected_paths(manifest_path: Path | None, raw_dir: Path) -> list[Path]:
    if manifest_path and manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        rows = manifest[manifest.get("selected", True).astype(bool)]
        if "downloaded" in rows.columns:
            rows = rows[rows["downloaded"].astype(bool)]
        return [Path(path) for path in rows["local_path"].dropna().astype(str)]
    return sorted(raw_dir.glob("*.h5ad"))


def update_manifest(manifest_path: Path, records: list[dict]) -> None:
    if not manifest_path.exists():
        return
    manifest = pd.read_csv(manifest_path)
    if "processed_path" not in manifest.columns:
        manifest["processed_path"] = ""
    manifest["error"] = manifest.get("error", "").fillna("").astype(str)
    manifest["processed_path"] = manifest["processed_path"].fillna("").astype(str)
    record_by_source = {record["source_path"]: record for record in records}
    for index, row in manifest.iterrows():
        record = record_by_source.get(str(row.get("local_path", "")))
        if not record:
            continue
        manifest.loc[index, "preprocessed"] = not bool(record.get("error"))
        manifest.loc[index, "processed_path"] = record.get("processed_path", "")
        manifest.loc[index, "error"] = record.get("error", "")
    manifest.to_csv(manifest_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize CELLxGENE source H5AD files for local ingestion.")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/single_cell_manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/single_cell"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/h5ad"))
    parser.add_argument("--report", type=Path, default=Path("data/manifests/single_cell_preprocess_report.csv"))
    parser.add_argument("--max-cells-for-umap", type=int, default=75_000)
    args = parser.parse_args()

    records = []
    for path in selected_paths(args.manifest, args.raw_dir):
        try:
            records.append(preprocess_file(path, args.output_dir, args.max_cells_for_umap))
        except Exception as exc:
            records.append(
                {
                    "dataset_id": path.stem,
                    "source_path": str(path),
                    "processed_path": "",
                    "n_obs": 0,
                    "n_vars": 0,
                    "has_umap": False,
                    "umap_status": "",
                    "error": str(exc),
                }
            )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(args.report, index=False)
    update_manifest(args.manifest, records)
    print(f"Wrote preprocess report to {args.report}")


if __name__ == "__main__":
    main()
