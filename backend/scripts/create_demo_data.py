from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd


DATASETS = [
    {
        "dataset_id": "lung_sc_tumor_atlas",
        "title": "Lung Tumor Immune Atlas",
        "description": "Single-cell RNA-seq cohort focused on immune and tumor compartments in lung adenocarcinoma.",
        "omics_type": "scRNA-seq",
        "species": "human",
        "disease": "lung cancer",
        "tissue": "lung",
        "condition": "tumor",
        "cell_types": ["T cell", "B cell", "Macrophage", "Tumor cell", "NK cell"],
        "samples": ["lung_tumor_1", "lung_tumor_2", "lung_tumor_3"],
        "n_obs": 72,
        "n_vars": 12,
    },
    {
        "dataset_id": "lung_sc_response_panel",
        "title": "Lung Immunotherapy Response Panel",
        "description": "Synthetic scRNA-seq panel contrasting responder and non-responder lung cancer samples.",
        "omics_type": "scRNA-seq",
        "species": "human",
        "disease": "lung cancer",
        "tissue": "lung",
        "condition": "post-treatment",
        "cell_types": ["T cell", "Dendritic cell", "Tumor cell", "Monocyte"],
        "samples": ["lung_resp_1", "lung_resp_2", "lung_nonresp_1"],
        "n_obs": 60,
        "n_vars": 14,
    },
    {
        "dataset_id": "colon_sc_inflammation_map",
        "title": "Colon Inflammation Cell Map",
        "description": "Single-cell RNA-seq view of epithelial and immune populations during active colitis.",
        "omics_type": "scRNA-seq",
        "species": "human",
        "disease": "colitis",
        "tissue": "colon",
        "condition": "inflamed",
        "cell_types": ["T cell", "Epithelial", "Fibroblast", "Macrophage"],
        "samples": ["colon_inf_1", "colon_inf_2", "colon_inf_3"],
        "n_obs": 54,
        "n_vars": 11,
    },
    {
        "dataset_id": "breast_bulk_expression_panel",
        "title": "Breast Bulk Expression Panel",
        "description": "Bulk RNA-seq expression profiles summarizing treatment-naive breast tumor biopsies.",
        "omics_type": "bulk RNA-seq",
        "species": "human",
        "disease": "breast cancer",
        "tissue": "breast",
        "condition": "baseline",
        "cell_types": ["Bulk profile"],
        "samples": ["breast_bulk_1", "breast_bulk_2", "breast_bulk_3", "breast_bulk_4"],
        "n_obs": 12,
        "n_vars": 16,
    },
    {
        "dataset_id": "liver_bulk_fibrosis_series",
        "title": "Liver Fibrosis Bulk Series",
        "description": "Bulk RNA-seq profiles across staged fibrosis samples collected from liver biopsies.",
        "omics_type": "bulk RNA-seq",
        "species": "human",
        "disease": "fibrosis",
        "tissue": "liver",
        "condition": "progressive",
        "cell_types": ["Bulk profile"],
        "samples": ["liver_bulk_f1", "liver_bulk_f2", "liver_bulk_f3"],
        "n_obs": 9,
        "n_vars": 16,
    },
    {
        "dataset_id": "colon_atac_regulatory_map",
        "title": "Colon Regulatory Accessibility Map",
        "description": "ATAC-seq accessibility profiles highlighting inflammatory regulatory programs in colon tissue.",
        "omics_type": "ATAC-seq",
        "species": "human",
        "disease": "colitis",
        "tissue": "colon",
        "condition": "inflamed",
        "cell_types": ["T cell", "Fibroblast", "Epithelial"],
        "samples": ["colon_atac_1", "colon_atac_2"],
        "n_obs": 36,
        "n_vars": 10,
    },
    {
        "dataset_id": "bone_marrow_atac_reference",
        "title": "Bone Marrow ATAC Reference",
        "description": "Reference ATAC-seq dataset covering hematopoietic compartments in healthy bone marrow.",
        "omics_type": "ATAC-seq",
        "species": "human",
        "disease": "healthy",
        "tissue": "bone marrow",
        "condition": "control",
        "cell_types": ["Stem cell", "B cell", "T cell", "Myeloid"],
        "samples": ["bm_atac_1", "bm_atac_2", "bm_atac_3"],
        "n_obs": 42,
        "n_vars": 10,
    },
    {
        "dataset_id": "brain_spatial_cortex_grid",
        "title": "Brain Cortex Spatial Grid",
        "description": "Spatial transcriptomics grid over healthy mouse cortex with region-specific neuron and glia signatures.",
        "omics_type": "spatial",
        "species": "mouse",
        "disease": "healthy",
        "tissue": "brain",
        "condition": "control",
        "cell_types": ["Neuron", "Astrocyte", "Microglia", "Oligodendrocyte"],
        "samples": ["brain_grid_1"],
        "n_obs": 48,
        "n_vars": 12,
    },
    {
        "dataset_id": "melanoma_spatial_margin",
        "title": "Melanoma Spatial Margin Survey",
        "description": "Spatial transcriptomics slices covering tumor core and invasive margin in melanoma lesions.",
        "omics_type": "spatial",
        "species": "human",
        "disease": "melanoma",
        "tissue": "skin",
        "condition": "tumor",
        "cell_types": ["T cell", "Tumor cell", "Fibroblast", "Endothelial"],
        "samples": ["mel_margin_1", "mel_margin_2"],
        "n_obs": 40,
        "n_vars": 12,
    },
    {
        "dataset_id": "ovarian_dna_variant_set",
        "title": "Ovarian DNA Variant Set",
        "description": "DNA-focused variant abundance matrix summarizing recurrent alterations across ovarian tumor samples.",
        "omics_type": "DNA",
        "species": "human",
        "disease": "ovarian cancer",
        "tissue": "ovary",
        "condition": "tumor",
        "cell_types": ["DNA profile"],
        "samples": ["ovary_dna_1", "ovary_dna_2", "ovary_dna_3"],
        "n_obs": 9,
        "n_vars": 18,
    },
    {
        "dataset_id": "glioma_dna_copy_number",
        "title": "Glioma Copy Number Survey",
        "description": "DNA copy-number style matrix for glioma samples across low- and high-grade lesions.",
        "omics_type": "DNA",
        "species": "human",
        "disease": "glioma",
        "tissue": "brain",
        "condition": "progressive",
        "cell_types": ["DNA profile"],
        "samples": ["glioma_dna_1", "glioma_dna_2"],
        "n_obs": 8,
        "n_vars": 18,
    },
]


def build_sample_file(output_dir: Path, spec: dict, sample_id: str, sample_index: int) -> None:
    file_path = output_dir / f"{spec['dataset_id']}__{sample_id}.h5ad"
    if file_path.exists():
        return

    seed = abs(hash(f"{spec['dataset_id']}::{sample_id}")) % (2**32)
    rng = np.random.default_rng(seed)
    sample_count = max(len(spec["samples"]), 1)
    n_obs = max(spec.get("n_obs", 24) // sample_count, 12)
    n_vars = spec.get("n_vars", 8)

    base_lambda = 1.8 if spec["omics_type"] in {"scRNA-seq", "spatial"} else 1.2
    X = rng.poisson(base_lambda, size=(n_obs, n_vars)).astype(float)
    X += rng.normal(0, 0.2, size=(n_obs, n_vars))
    X = np.clip(X, a_min=0, a_max=None)

    sample_ids = [sample_id] * n_obs
    cell_types = [spec["cell_types"][i % len(spec["cell_types"])] for i in range(n_obs)]
    condition_value = spec["condition"]
    if spec["condition"] == "post-treatment":
        condition_value = "responder" if sample_index < max(sample_count - 1, 1) else "non-responder"
    conditions = [condition_value] * n_obs

    obs = pd.DataFrame(
        {
            "sample_id": sample_ids,
            "cell_type": cell_types,
            "cluster": [f"C{i % max(3, min(6, len(spec['cell_types']) + 1))}" for i in range(n_obs)],
            "disease": [spec["disease"]] * n_obs,
            "tissue": [spec["tissue"]] * n_obs,
            "condition": conditions,
        }
    )
    obs.index = [f"{sample_id}_row_{i}" for i in range(n_obs)]

    feature_prefix = {
        "scRNA-seq": "GENE",
        "bulk RNA-seq": "GENE",
        "ATAC-seq": "PEAK",
        "spatial": "GENE",
        "DNA": "LOCUS",
    }.get(spec["omics_type"], "FEATURE")
    var = pd.DataFrame(index=[f"{feature_prefix}_{i + 1}" for i in range(n_vars)])

    adata = ad.AnnData(X=X, obs=obs, var=var)
    adata.uns["dataset_metadata"] = {
        "dataset_id": f"{spec['dataset_id']}__{sample_id}",
        "title": spec["title"],
        "description": spec["description"],
        "species": spec["species"],
    }
    adata.uns["sample_metadata"] = {
        "sample_id": sample_id,
        "sample_code": sample_id,
        "title": f"{spec['title']} · {sample_id}",
        "description": spec["description"],
        "group_code": "plain_low_altitude",
    }

    adata.obsm["X_umap"] = rng.normal(size=(n_obs, 2))

    adata.write_h5ad(file_path)


def main() -> None:
    output_dir = Path("/data/h5ad")
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec in DATASETS:
        if spec["omics_type"] != "scRNA-seq":
            continue
        for sample_index, sample_id in enumerate(spec["samples"]):
            build_sample_file(output_dir, spec, sample_id, sample_index)


if __name__ == "__main__":
    main()
