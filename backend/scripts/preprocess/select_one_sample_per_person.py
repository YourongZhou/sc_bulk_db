import argparse
from pathlib import Path

import anndata as ad
import pandas as pd


def choose_sample_id(obs: pd.DataFrame, sample_column: str) -> tuple[str, dict[str, int]]:
    counts = obs[sample_column].astype("string").fillna("NA").value_counts()
    selected = counts.sort_values(ascending=False, kind="stable").index[0]
    return str(selected), {str(key): int(value) for key, value in counts.to_dict().items()}


def filter_file(
    source_path: Path,
    output_dir: Path,
    person_column: str,
    sample_column: str,
) -> dict[str, str | int]:
    adata = ad.read_h5ad(source_path)
    obs = adata.obs.copy()
    if person_column not in obs.columns:
        raise KeyError(f"{source_path}: missing person column {person_column!r}")
    if sample_column not in obs.columns:
        raise KeyError(f"{source_path}: missing sample column {sample_column!r}")

    person_ids = obs[person_column].astype("string").fillna("NA").unique().tolist()
    if len(person_ids) != 1:
        raise ValueError(f"{source_path}: expected exactly one {person_column}, found {person_ids}")

    selected_sample_id, sample_counts = choose_sample_id(obs, sample_column)
    mask = obs[sample_column].astype("string").fillna("NA") == selected_sample_id
    filtered = adata[mask.to_numpy()].copy()
    filtered.obs["sample_id"] = selected_sample_id
    filtered.uns["source_file"] = str(source_path)
    filtered.uns["selected_sample_column"] = sample_column
    filtered.uns["selected_sample_id"] = selected_sample_id
    filtered.uns["person_column"] = person_column
    filtered.uns["person_id"] = str(person_ids[0])

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / source_path.name
    filtered.write_h5ad(output_path, compression="gzip")

    return {
        "source_path": str(source_path),
        "output_path": str(output_path),
        "person_id": str(person_ids[0]),
        "selected_sample_id": selected_sample_id,
        "n_obs_before": int(adata.n_obs),
        "n_obs_after": int(filtered.n_obs),
        "n_unique_sample_ids_before": int(len(sample_counts)),
        "sample_counts_before": str(sample_counts),
    }


def write_manifest(records: list[dict[str, str | int]], manifest_path: Path) -> None:
    rows = []
    for record in records:
        rows.append(
            {
                "local_path": record["output_path"],
                "selected": True,
                "downloaded": True,
                "preprocessed": False,
                "ingested": False,
                "person_id": record["person_id"],
                "selected_sample_id": record["selected_sample_id"],
                "n_obs_before": record["n_obs_before"],
                "n_obs_after": record["n_obs_after"],
                "n_unique_sample_ids_before": record["n_unique_sample_ids_before"],
                "sample_counts_before": record["sample_counts_before"],
                "error": "",
            }
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(manifest_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Keep one sample_id per person-level H5AD file and prepare a manifest for preprocessing."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/single_cell/h5ad/pbmc_atlas_1_split_combat20"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/single_cell/pbmc_atlas_1_combat20_one_sample"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/single_cell_manifest.csv"),
    )
    parser.add_argument("--person-column", default="COMBAT_ID")
    parser.add_argument("--sample-column", default="scRNASeq_sample_ID")
    args = parser.parse_args()

    records = []
    for source_path in sorted(args.input_dir.glob("*.h5ad")):
        record = filter_file(source_path, args.output_dir, args.person_column, args.sample_column)
        records.append(record)
        print(
            f"wrote {record['output_path']} for {record['person_id']} "
            f"using sample_id={record['selected_sample_id']} ({record['n_obs_after']} obs)"
        )

    write_manifest(records, args.manifest)
    print(f"wrote manifest csv: {args.manifest}")


if __name__ == "__main__":
    main()
