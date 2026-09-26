#!/usr/bin/env python3
"""Compare observed EPH and Census-target predictive agglomerate releases.

This is commissioning only. It creates no new estimand and does not aggregate
or transform poverty science beyond subtracting two already-released estimates.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from poverty_pipeline.release_v2 import verify_estimate_release


class AgglomerateCommissioningError(ValueError):
    pass


def _load_release(root: Path, role: str) -> tuple[pd.DataFrame, dict]:
    verify_estimate_release(root)
    manifest = json.loads((root / "release_manifest.json").read_text(encoding="utf-8"))
    with (root / "poverty_estimates.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    frame = pd.DataFrame(rows)
    frame["estimate"] = pd.to_numeric(frame["estimate"], errors="raise")
    frame["weighted_numerator"] = pd.to_numeric(
        frame["weighted_numerator"], errors="raise"
    )
    frame["weighted_denominator"] = pd.to_numeric(
        frame["weighted_denominator"], errors="raise"
    )
    aggregate = manifest.get("aggregate_geography")
    if aggregate != {"level": "eph_coverage", "id": "EPH_TOTAL"}:
        raise AgglomerateCommissioningError(
            f"{role} release must declare eph_coverage/EPH_TOTAL"
        )
    levels = set(frame["geography_level"])
    if levels != {"eph_agglomerate", "eph_coverage"}:
        raise AgglomerateCommissioningError(
            f"{role} release has unexpected geography levels: {sorted(levels)}"
        )
    return frame, manifest


def compare_releases(
    observed_root: Path,
    predictive_root: Path,
) -> tuple[pd.DataFrame, dict]:
    observed, observed_manifest = _load_release(observed_root, "observed")
    predictive, predictive_manifest = _load_release(predictive_root, "predictive")

    observed_period = str(observed_manifest["estimation_period"])
    predictive_period = str(predictive_manifest["estimation_period"])
    if observed_period != predictive_period:
        raise AgglomerateCommissioningError(
            f"period mismatch: {observed_period} != {predictive_period}"
        )

    def select(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        keep = frame[
            (frame["universe"] == "persons")
            & (frame["estimand"] == "fgt0")
            & (frame["concept"].isin(["poverty", "indigence"]))
        ].copy()
        key = ["geography_level", "geography_id", "concept"]
        if keep.duplicated(key).any():
            raise AgglomerateCommissioningError(f"{prefix} release has duplicate commissioning keys")
        return keep[
            key + ["estimate", "weighted_numerator", "weighted_denominator"]
        ].rename(
            columns={
                "estimate": f"{prefix}_estimate",
                "weighted_numerator": f"{prefix}_weighted_numerator",
                "weighted_denominator": f"{prefix}_weighted_denominator",
            }
        )

    left = select(observed, "observed")
    right = select(predictive, "predictive")
    merged = left.merge(
        right,
        on=["geography_level", "geography_id", "concept"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        missing = merged.loc[
            ~merged["_merge"].eq("both"),
            ["geography_level", "geography_id", "concept", "_merge"],
        ].to_dict("records")
        raise AgglomerateCommissioningError(
            f"observed/predictive commissioning inventories differ: {missing[:20]}"
        )
    merged = merged.drop(columns="_merge")
    aglo_ids = set(
        merged.loc[
            merged["geography_level"] == "eph_agglomerate", "geography_id"
        ].astype(str)
    )
    if len(aglo_ids) != 32:
        raise AgglomerateCommissioningError(
            f"commissioning requires 32 agglomerates, got {len(aglo_ids)}"
        )
    aggregate_ids = set(
        merged.loc[
            merged["geography_level"] == "eph_coverage", "geography_id"
        ].astype(str)
    )
    if aggregate_ids != {"EPH_TOTAL"}:
        raise AgglomerateCommissioningError(
            f"commissioning aggregate identity mismatch: {sorted(aggregate_ids)}"
        )

    merged.insert(0, "period", observed_period)
    merged["delta"] = merged["predictive_estimate"] - merged["observed_estimate"]
    merged["delta_pp"] = 100.0 * merged["delta"]
    merged = merged.sort_values(
        ["concept", "geography_level", "geography_id"], ignore_index=True
    )

    summary = {
        "schema_version": "eph-agglomerate-observed-predictive-commissioning/v1",
        "period": observed_period,
        "agglomerate_count": 32,
        "aggregate_geography": {"level": "eph_coverage", "id": "EPH_TOTAL"},
        "observed_release_id": observed_manifest["release_id"],
        "predictive_release_id": predictive_manifest["release_id"],
        "new_estimand_created": False,
        "rows": len(merged),
        "eph_total": {
            row.concept: {
                "observed": float(row.observed_estimate),
                "predictive": float(row.predictive_estimate),
                "delta_pp": float(row.delta_pp),
            }
            for row in merged.loc[
                merged["geography_level"].eq("eph_coverage")
            ].itertuples()
        },
        "largest_absolute_agglomerate_delta_pp": {
            concept: (
                subset.assign(abs_delta=subset["delta_pp"].abs())
                .sort_values("abs_delta", ascending=False)
                .head(5)[
                    ["geography_id", "observed_estimate", "predictive_estimate", "delta_pp"]
                ]
                .to_dict("records")
            )
            for concept, subset in merged.loc[
                merged["geography_level"].eq("eph_agglomerate")
            ].groupby("concept")
        },
    }
    return merged, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed-release", type=Path, required=True)
    parser.add_argument("--predictive-release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows, summary = compare_releases(
        args.observed_release.resolve(),
        args.predictive_release.resolve(),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    rows.to_csv(args.output / "agglomerate_comparison.csv", index=False)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary["eph_total"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
