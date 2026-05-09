import argparse
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm


MANIFEST_COLUMNS = [
    "dataset_id",
    "title",
    "collection_name",
    "cell_count",
    "assay",
    "tissue",
    "tissue_general",
    "disease",
    "source",
    "fallback_reason",
    "local_path",
    "selected",
    "downloaded",
    "preprocessed",
    "ingested",
    "error",
]


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_") or "dataset"


def load_census_candidates(limit: int, max_cells: int) -> pd.DataFrame:
    try:
        import cellxgene_census
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install backend/scripts/download/requirements.txt first."
        ) from exc

    column_names = [
        "dataset_id",
        "assay",
        "tissue",
        "tissue_general",
        "disease",
        "is_primary_data",
    ]
    filters = [
        (
            "blood_or_pbmc",
            "is_primary_data == True and (tissue_general == 'blood' or tissue == 'blood' or tissue == 'peripheral blood mononuclear cell')",
        ),
        ("blood_general", "is_primary_data == True and tissue_general == 'blood'"),
        ("all_primary_fallback", "is_primary_data == True"),
    ]

    frames: list[pd.DataFrame] = []
    with cellxgene_census.open_soma(census_version="stable") as census:
        datasets = census["census_info"]["datasets"].read().concat().to_pandas()
        for source, value_filter in filters:
            if sum(len(frame) for frame in frames) >= limit * 2:
                break
            try:
                obs = cellxgene_census.get_obs(
                    census,
                    "homo_sapiens",
                    value_filter=value_filter,
                    column_names=column_names,
                )
            except Exception as exc:
                print(f"Skipping filter {source}: {exc}")
                continue

            obs_df = obs.to_pandas() if hasattr(obs, "to_pandas") else pd.DataFrame(obs)
            if obs_df.empty:
                continue
            grouped = (
                obs_df.groupby("dataset_id", dropna=False)
                .agg(
                    cell_count=("dataset_id", "size"),
                    assay=("assay", lambda values: "; ".join(sorted({str(v) for v in values.dropna()})[:5])),
                    tissue=("tissue", lambda values: "; ".join(sorted({str(v) for v in values.dropna()})[:5])),
                    tissue_general=(
                        "tissue_general",
                        lambda values: "; ".join(sorted({str(v) for v in values.dropna()})[:5]),
                    ),
                    disease=("disease", lambda values: "; ".join(sorted({str(v) for v in values.dropna()})[:5])),
                )
                .reset_index()
            )
            grouped["source"] = source
            grouped["fallback_reason"] = "" if source != "all_primary_fallback" else "not enough blood/PBMC candidates"
            frames.append(grouped)

        if not frames:
            return pd.DataFrame(columns=MANIFEST_COLUMNS)

        candidates = pd.concat(frames, ignore_index=True).drop_duplicates("dataset_id", keep="first")
        candidates = candidates[candidates["cell_count"] <= max_cells].copy()
        source_rank = {"blood_or_pbmc": 0, "blood_general": 1, "all_primary_fallback": 2}
        candidates["source_rank"] = candidates["source"].map(source_rank).fillna(9)
        candidates = candidates.sort_values(["source_rank", "cell_count"], ascending=[True, True]).head(limit)

        keep_cols = [
            column
            for column in ["dataset_id", "dataset_title", "title", "collection_name", "collection_id"]
            if column in datasets.columns
        ]
        if keep_cols:
            candidates = candidates.merge(
                datasets[keep_cols].drop_duplicates("dataset_id"),
                on="dataset_id",
                how="left",
            )

    candidates["title"] = candidates.get("dataset_title", candidates.get("title", candidates["dataset_id"]))
    if "collection_name" not in candidates:
        candidates["collection_name"] = ""
    return candidates


def write_manifest(df: pd.DataFrame, manifest_path: Path, raw_dir: Path) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        dataset_id = str(row["dataset_id"])
        local_path = raw_dir / f"{safe_name(dataset_id)}.h5ad"
        rows.append(
            {
                "dataset_id": dataset_id,
                "title": row.get("title", dataset_id),
                "collection_name": row.get("collection_name", ""),
                "cell_count": int(row.get("cell_count", 0)),
                "assay": row.get("assay", ""),
                "tissue": row.get("tissue", ""),
                "tissue_general": row.get("tissue_general", ""),
                "disease": row.get("disease", ""),
                "source": row.get("source", ""),
                "fallback_reason": row.get("fallback_reason", ""),
                "local_path": str(local_path),
                "selected": True,
                "downloaded": local_path.exists() and local_path.stat().st_size > 0,
                "preprocessed": False,
                "ingested": False,
                "error": "",
            }
        )
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)
    return manifest


def download_selected(manifest_path: Path) -> None:
    try:
        import cellxgene_census
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install backend/scripts/download/requirements.txt first."
        ) from exc

    manifest = pd.read_csv(manifest_path)
    manifest["error"] = manifest.get("error", "").fillna("").astype(str)
    for index, row in tqdm(manifest.iterrows(), total=len(manifest), desc="Downloading CELLxGENE H5AD"):
        if not bool(row.get("selected", True)):
            continue
        local_path = Path(str(row["local_path"]))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists() and local_path.stat().st_size > 0:
            manifest.loc[index, "downloaded"] = True
            continue
        try:
            cellxgene_census.download_source_h5ad(str(row["dataset_id"]), to_path=str(local_path))
            manifest.loc[index, "downloaded"] = local_path.exists() and local_path.stat().st_size > 0
            manifest.loc[index, "error"] = ""
        except Exception as exc:
            manifest.loc[index, "downloaded"] = False
            manifest.loc[index, "error"] = str(exc)
        manifest.to_csv(manifest_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Find and optionally download CELLxGENE blood/PBMC source H5AD files.")
    parser.add_argument("--limit", type=int, default=18)
    parser.add_argument("--max-cells", type=int, default=250_000)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/single_cell_manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/single_cell"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    if args.download and args.manifest.exists():
        download_selected(args.manifest)
        return

    candidates = load_census_candidates(args.limit, args.max_cells)
    manifest = write_manifest(candidates, args.manifest, args.raw_dir)
    print(f"Wrote {len(manifest)} candidates to {args.manifest}")
    if args.download:
        download_selected(args.manifest)


if __name__ == "__main__":
    main()
