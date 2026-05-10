import argparse
import gzip
from collections.abc import Iterable
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a GEO bulk RNA-seq series with count matrix + SOFT metadata into an ingestible H5AD."
    )
    parser.add_argument("--series-id", default="GSE198533")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bulk/GSE198533"))
    parser.add_argument("--counts-path", type=Path, default=None)
    parser.add_argument("--soft-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/h5ad"))
    parser.add_argument("--value-kind", choices=["count", "fpkm"], default="count")
    parser.add_argument("--min-count", type=int, default=10)
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument("--species", default="human")
    parser.add_argument("--omics-type", default="bulk RNA-seq")
    parser.add_argument("--case-disease-label", default="Behcet's disease")
    parser.add_argument("--control-disease-label", default="healthy")
    return parser.parse_args()


def counts_path_for(raw_dir: Path, series_id: str, override: Path | None) -> Path:
    return override or raw_dir / f"{series_id}_Raw_gene_counts_matrix.csv.gz"


def soft_path_for(raw_dir: Path, series_id: str, override: Path | None) -> Path:
    return override or raw_dir / f"{series_id}_family.soft.gz"


def read_geo_matrix(path: Path) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    frame = pd.read_csv(path)
    if "gene_id" not in frame.columns:
        raise ValueError(f"{path}: expected a gene_id column")

    count_columns = [column for column in frame.columns if column.endswith("_count")]
    fpkm_columns = [column for column in frame.columns if column.endswith("_fpkm")]
    if not count_columns:
        raise ValueError(f"{path}: no *_count columns found")

    counts = frame[["gene_id", *count_columns]].copy()
    counts.columns = ["gene_id", *[column.removesuffix("_count") for column in count_columns]]
    counts = counts.set_index("gene_id")
    counts = counts.apply(pd.to_numeric, errors="coerce").fillna(0)

    if not fpkm_columns:
        return counts, None

    fpkm = frame[["gene_id", *fpkm_columns]].copy()
    fpkm.columns = ["gene_id", *[column.removesuffix("_fpkm") for column in fpkm_columns]]
    fpkm = fpkm.set_index("gene_id")
    fpkm = fpkm.apply(pd.to_numeric, errors="coerce").fillna(0)
    return counts, fpkm


def iter_soft_lines(path: Path) -> Iterable[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            yield raw_line.rstrip("\n")


def parse_relation_accession(value: str, prefix: str) -> str | None:
    if not value.startswith(prefix):
        return None
    return value.rsplit("=", 1)[-1].strip().split("/")[-1]


def parse_characteristic(value: str) -> tuple[str, str]:
    if ":" not in value:
        return value.strip().lower(), ""
    key, raw = value.split(":", 1)
    return key.strip().lower(), raw.strip()


def parse_soft_samples(path: Path) -> tuple[dict[str, str], pd.DataFrame]:
    series_meta: dict[str, str] = {}
    sample_rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in iter_soft_lines(path):
        if line.startswith("^SERIES = "):
            continue
        if line.startswith("!Series_title = "):
            series_meta["title"] = line.removeprefix("!Series_title = ").strip()
            continue
        if line.startswith("!Series_summary = "):
            series_meta["summary"] = line.removeprefix("!Series_summary = ").strip()
            continue
        if line.startswith("!Series_overall_design = "):
            series_meta["overall_design"] = line.removeprefix("!Series_overall_design = ").strip()
            continue

        if line.startswith("^SAMPLE = "):
            if current:
                sample_rows.append(current)
            current = {"sample_geo_accession": line.removeprefix("^SAMPLE = ").strip()}
            continue

        if current is None or not line.startswith("!Sample_"):
            continue

        if line.startswith("!Sample_title = "):
            current["sample_title"] = line.removeprefix("!Sample_title = ").strip()
        elif line.startswith("!Sample_source_name_ch1 = "):
            current["source_name"] = line.removeprefix("!Sample_source_name_ch1 = ").strip()
        elif line.startswith("!Sample_library_strategy = "):
            current["assay"] = line.removeprefix("!Sample_library_strategy = ").strip()
        elif line.startswith("!Sample_characteristics_ch1 = "):
            key, value = parse_characteristic(line.removeprefix("!Sample_characteristics_ch1 = ").strip())
            current[key] = value
        elif line.startswith("!Sample_relation = "):
            relation = line.removeprefix("!Sample_relation = ").strip()
            sra = parse_relation_accession(relation, "SRA:")
            biosample = parse_relation_accession(relation, "BioSample:")
            if sra:
                current["sra_accession"] = sra
            if biosample:
                current["biosample_accession"] = biosample

    if current:
        sample_rows.append(current)

    metadata = pd.DataFrame(sample_rows)
    if metadata.empty or "sample_title" not in metadata.columns:
        raise ValueError(f"{path}: failed to parse GEO sample metadata")
    metadata["sample_title"] = metadata["sample_title"].astype(str)
    return series_meta, metadata.set_index("sample_title")


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


def infer_tissue(source_name: str | None) -> str:
    value = (source_name or "").strip()
    if not value:
        return "PBMC"
    if "pbmc" in value.lower():
        return "PBMC"
    return value


def infer_disease(condition: str, case_disease_label: str, control_disease_label: str) -> str:
    lowered = condition.lower()
    if "healthy" in lowered or "control" in lowered:
        return control_disease_label
    return case_disease_label or condition or "unknown"


def build_obs(
    sample_ids: list[str],
    sample_metadata: pd.DataFrame,
    case_disease_label: str,
    control_disease_label: str,
) -> pd.DataFrame:
    missing = [sample_id for sample_id in sample_ids if sample_id not in sample_metadata.index]
    if missing:
        raise ValueError(f"Sample metadata missing rows for: {missing}")

    obs = sample_metadata.loc[sample_ids].copy()
    condition = obs.get("condition", pd.Series("unknown", index=obs.index)).fillna("unknown").astype(str)
    sex = obs.get("sex", obs.get("Sex", pd.Series("unknown", index=obs.index))).fillna("unknown").astype(str)
    age = obs.get("age", pd.Series("", index=obs.index)).fillna("").astype(str)
    source_name = obs.get("source_name", pd.Series("", index=obs.index)).fillna("").astype(str)
    obs = obs.assign(
        sample_id=obs.index.astype(str),
        cell_type="Bulk profile",
        cluster="bulk",
        disease=[infer_disease(value, case_disease_label, control_disease_label) for value in condition],
        tissue=[infer_tissue(value) for value in source_name],
        condition=condition,
        sex=sex.str.lower().replace({"nan": "unknown", "": "unknown"}),
        age=age.replace({"nan": "", "None": ""}),
        donor_id=obs.index.astype(str),
    )
    return obs


def main() -> None:
    args = parse_args()
    counts_path = counts_path_for(args.raw_dir, args.series_id, args.counts_path)
    soft_path = soft_path_for(args.raw_dir, args.series_id, args.soft_path)

    counts, fpkm = read_geo_matrix(counts_path)
    series_meta, sample_metadata = parse_soft_samples(soft_path)
    if args.value_kind == "fpkm":
        if fpkm is None:
            raise ValueError(f"{counts_path}: no *_fpkm columns available")
        matrix = np.log2(fpkm + 1)
        matrix_note = "X stores log2(FPKM + 1) from the GEO supplementary matrix"
    else:
        matrix = log_cpm(counts, args.min_count, args.min_samples)
        matrix_note = "X stores log2(CPM + 1) derived from raw counts"

    sample_ids = list(matrix.columns)
    obs = build_obs(sample_ids, sample_metadata, args.case_disease_label, args.control_disease_label)

    adata = ad.AnnData(
        X=matrix.T.to_numpy(dtype=np.float32),
        obs=obs,
        var=pd.DataFrame(index=matrix.index.astype(str)),
    )
    adata.layers["counts"] = counts.loc[matrix.index, sample_ids].T.to_numpy(dtype=np.float32)
    if fpkm is not None:
        adata.layers["fpkm"] = fpkm.loc[matrix.index, sample_ids].T.to_numpy(dtype=np.float32)
    adata.obsm["X_pca"] = build_pca(matrix)
    adata.uns["dataset_metadata"] = {
        "dataset_id": args.series_id,
        "title": series_meta.get("title", args.series_id),
        "description": series_meta.get("summary")
        or series_meta.get("overall_design")
        or f"GEO bulk RNA-seq series {args.series_id}",
        "omics_type": args.omics_type,
        "species": args.species,
    }
    adata.uns["preprocessing_notes"] = [
        f"source_counts={counts_path}",
        f"source_soft={soft_path}",
        f"value_kind={args.value_kind}",
        matrix_note,
        "layers['counts'] stores the raw count matrix",
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{args.series_id}.h5ad"
    adata.write_h5ad(output_path, compression="gzip")
    print(f"Wrote {output_path}")
    print(f"n_obs={adata.n_obs} n_vars={adata.n_vars}")


if __name__ == "__main__":
    main()
