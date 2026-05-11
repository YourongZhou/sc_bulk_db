import argparse
import re
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd


def make_safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe or "unknown_value"


def normalize_group_values(obs: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    normalized = obs[group_columns].copy()
    for column in group_columns:
        normalized[column] = normalized[column].astype("string").fillna("NA")
    return normalized


def group_summary(obs: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    normalized = normalize_group_values(obs, group_columns)
    counts = (
        normalized.groupby(group_columns, dropna=False)
        .size()
        .reset_index(name="n_obs")
        .sort_values(group_columns, kind="stable")
        .reset_index(drop=True)
    )
    return counts


def print_summary(summary: pd.DataFrame, group_columns: list[str]) -> None:
    print(f"group columns: {group_columns}")
    print(f"number of groups: {len(summary)}")
    print(summary.to_string(index=False))


def select_summary_groups(
    summary: pd.DataFrame,
    random_sample_groups: int | None,
    random_seed: int,
) -> pd.DataFrame:
    if random_sample_groups is None:
        return summary
    if random_sample_groups <= 0:
        raise ValueError("--random-sample-groups must be greater than 0")
    if random_sample_groups >= len(summary):
        return summary
    selected = summary.sample(n=random_sample_groups, random_state=random_seed).copy()
    return selected.reset_index(drop=True)


def split_by_groups(
    input_path: Path,
    output_dir: Path,
    group_columns: list[str],
    compression: str | None,
    name_prefix: str,
    manifest_path: Path | None,
    selected_summary: pd.DataFrame | None = None,
) -> None:
    adata = ad.read_h5ad(input_path)
    normalized = normalize_group_values(adata.obs, group_columns)
    summary = selected_summary if selected_summary is not None else group_summary(adata.obs, group_columns)

    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str | int]] = []

    for index, row in summary.iterrows():
        output_name = f"{name_prefix}_{index + 1}"
        mask = pd.Series(True, index=normalized.index)
        for column in group_columns:
            mask &= normalized[column] == row[column]
        subset = adata[np.asarray(mask, dtype=bool)].copy()
        subset.uns["source_file"] = str(input_path)
        subset.uns["group_columns"] = group_columns
        subset.uns["group_values"] = {column: str(row[column]) for column in group_columns}
        subset.uns["dataset_metadata"] = {
            "dataset_id": output_name,
            "title": output_name,
            "description": f"Subset of {input_path.name} for "
            + ", ".join(f"{column}={row[column]}" for column in group_columns),
            "omics_type": "CITE-seq",
            "species": "human",
        }
        output_path = output_dir / f"{output_name}.h5ad"
        subset.write_h5ad(output_path, compression=compression)
        print(
            "wrote"
            f" {output_path} ({subset.n_obs} obs)"
            f" from " + ", ".join(f"{column}={row[column]}" for column in group_columns)
        )
        record = {
            "dataset_name": output_name,
            "output_path": str(output_path),
            "n_obs": int(subset.n_obs),
        }
        for column in group_columns:
            record[column] = str(row[column])
        records.append(record)

    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(records).to_csv(manifest_path, index=False)
        print(f"wrote manifest csv: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect an h5ad file and optionally split it into one file per group."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("/home/luting/nfs/CITEseq_data/pbmc atlas/6/data.h5ad"),
        help="Path to the source h5ad file.",
    )
    parser.add_argument(
        "--group-columns",
        nargs="+",
        default=["batch", "time"],
        help="Observation columns used together to define output groups.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/luting/projects/sc_bulk_db/data/single_cell/h5ad/pbmc_atlas_6_split_24"),
        help="Directory to write per-group h5ad files into when --write is used.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=Path("/home/luting/projects/sc_bulk_db/data/single_cell/h5ad/pbmc_atlas_6_split_24/summary.csv"),
        help="Optional CSV path for writing the group summary.",
    )
    parser.add_argument(
        "--manifest-csv",
        type=Path,
        default=Path("/home/luting/projects/sc_bulk_db/data/single_cell/h5ad/pbmc_atlas_6_split_24/manifest.csv"),
        help="Optional CSV path for writing the dataset_name to group mapping.",
    )
    parser.add_argument(
        "--name-prefix",
        default="data",
        help="Prefix for output dataset names such as data_1, data_2, ...",
    )
    parser.add_argument(
        "--random-sample-groups",
        type=int,
        default=None,
        help="Randomly select this many groups from the summary before writing output files.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed used with --random-sample-groups.",
    )
    parser.add_argument(
        "--compression",
        choices=["gzip", "lzf", "none"],
        default="gzip",
        help="Compression used for output h5ad files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write one h5ad file per group. Without this flag, the script only prints a summary.",
    )
    args = parser.parse_args()

    adata = ad.read_h5ad(args.input, backed="r")
    missing_columns = [column for column in args.group_columns if column not in adata.obs.columns]
    if missing_columns:
        raise KeyError(f"Columns not found in obs: {missing_columns}. Available columns: {list(adata.obs.columns)}")

    summary = group_summary(adata.obs, args.group_columns)
    selected_summary = select_summary_groups(summary, args.random_sample_groups, args.random_seed)
    print(f"input: {args.input}")
    print(f"shape: {adata.n_obs} obs x {adata.n_vars} vars")
    print(f"obs columns: {list(adata.obs.columns)}")
    print_summary(selected_summary, args.group_columns)
    if args.random_sample_groups is not None:
        print(
            f"randomly selected {len(selected_summary)} of {len(summary)} groups "
            f"with seed={args.random_seed}"
        )

    if args.summary_csv is not None:
        args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
        selected_summary.to_csv(args.summary_csv, index=False)
        print(f"wrote summary csv: {args.summary_csv}")

    if args.write:
        compression = None if args.compression == "none" else args.compression
        split_by_groups(
            args.input,
            args.output_dir,
            args.group_columns,
            compression,
            args.name_prefix,
            args.manifest_csv,
            selected_summary,
        )


if __name__ == "__main__":
    main()
