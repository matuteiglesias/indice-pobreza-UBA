#!/usr/bin/env python3
"""Build a governed EPH-agglomerate -> poverty basket-region binding.

The script deliberately reuses Telescope-A household microscopes, where native
EPH REGION has already been converted to the canonical six basket-region IDs.
It performs no new poverty computation and no geography inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

ALLOWED_REGIONS = {
    "gran_buenos_aires",
    "cuyo",
    "noreste",
    "noroeste",
    "pampeana",
    "patagonia",
}


class AgglomerateRegionBindingError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_inventory(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"eph_agglomerate_id"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise AgglomerateRegionBindingError(
            f"agglomerate inventory missing columns: {missing}"
        )
    frame["eph_agglomerate_id"] = frame["eph_agglomerate_id"].astype(str).str.zfill(2)
    if frame["eph_agglomerate_id"].duplicated().any():
        raise AgglomerateRegionBindingError("agglomerate inventory IDs must be unique")
    if not frame["eph_agglomerate_id"].str.fullmatch(r"[0-9]{2}").all():
        raise AgglomerateRegionBindingError("inventory agglomerate IDs must preserve two digits")
    return frame


def derive_binding(
    microscopes: list[pd.DataFrame],
    expected_ids: set[str],
) -> tuple[list[dict], dict]:
    if not microscopes:
        raise AgglomerateRegionBindingError("at least one Telescope-A microscope is required")
    rows = []
    for index, frame in enumerate(microscopes):
        missing = sorted({"AGLOMERADO", "basket_region"} - set(frame.columns))
        if missing:
            raise AgglomerateRegionBindingError(
                f"microscope[{index}] missing columns: {missing}"
            )
        local = frame[["AGLOMERADO", "basket_region"]].copy()
        aglo_num = pd.to_numeric(local["AGLOMERADO"], errors="coerce")
        if aglo_num.isna().any() or ((aglo_num % 1) != 0).any():
            raise AgglomerateRegionBindingError(
                f"microscope[{index}] contains invalid AGLOMERADO"
            )
        local["eph_agglomerate_id"] = aglo_num.astype(int).astype(str).str.zfill(2)
        local["basket_region"] = local["basket_region"].astype(str).str.strip()
        if not local["basket_region"].isin(ALLOWED_REGIONS).all():
            bad = sorted(set(local.loc[~local["basket_region"].isin(ALLOWED_REGIONS), "basket_region"]))
            raise AgglomerateRegionBindingError(f"unknown basket regions: {bad}")
        rows.append(local[["eph_agglomerate_id", "basket_region"]])

    combined = pd.concat(rows, ignore_index=True).drop_duplicates()
    conflicts = (
        combined.groupby("eph_agglomerate_id")["basket_region"].nunique().loc[lambda s: s != 1]
    )
    if not conflicts.empty:
        raise AgglomerateRegionBindingError(
            f"agglomerates map to multiple basket regions: {conflicts.index.tolist()}"
        )

    observed_ids = set(combined["eph_agglomerate_id"])
    if observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise AgglomerateRegionBindingError(
            f"EPH/A7 agglomerate inventory mismatch: missing={missing} extra={extra}"
        )

    mapping = (
        combined.sort_values(["eph_agglomerate_id", "basket_region"])
        .drop_duplicates("eph_agglomerate_id")
        .reset_index(drop=True)
    )
    result = [
        {
            "geography_level": "eph_agglomerate",
            "geography_id": row.eph_agglomerate_id,
            "poverty_region_id": row.basket_region,
        }
        for row in mapping.itertuples()
    ]
    qa = {
        "agglomerate_count": len(result),
        "expected_id_count": len(expected_ids),
        "exact_inventory_match": True,
        "region_count": mapping["basket_region"].nunique(),
        "regions": sorted(mapping["basket_region"].unique().tolist()),
        "conflicting_agglomerates": [],
        "mapping_source": "Telescope-A household microscope AGLOMERADO x basket_region",
        "new_poverty_computation": False,
        "spatial_inference": False,
    }
    return result, qa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--telescope-a-households",
        type=Path,
        action="append",
        required=True,
        help="Repeat for each governed Telescope-A household_microscope.csv.",
    )
    parser.add_argument("--agglomerate-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    inventory = _read_inventory(args.agglomerate_inventory)
    expected_ids = set(inventory["eph_agglomerate_id"])
    microscopes = [
        pd.read_csv(path, dtype=str, keep_default_na=False)
        for path in args.telescope_a_households
    ]
    rows, qa = derive_binding(microscopes, expected_ids)
    payload = {
        "schema_version": "poverty-threshold-area-binding/eph-agglomerate-v1",
        "release_id": "eph-agglomerate-poverty-region-binding-v1",
        "geography_level": "eph_agglomerate",
        "region_field": "poverty_region_id",
        "rows": rows,
        "qa": qa,
        "parents": {
            "agglomerate_inventory": {
                "path_name": args.agglomerate_inventory.name,
                "sha256": sha256(args.agglomerate_inventory),
            },
            "telescope_a_households": [
                {"path_name": path.name, "sha256": sha256(path)}
                for path in args.telescope_a_households
            ],
        },
        "limitations": [
            "This is poverty-line policy, not intrinsic geography.",
            "The binding reuses Telescope-A's already-governed EPH REGION to basket-region semantics.",
            "No population weights, poverty states, welfare estimates or spatial operations are used to create the binding.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["geography_level", "geography_id", "poverty_region_id"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
