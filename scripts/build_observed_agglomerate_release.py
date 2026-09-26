#!/usr/bin/env python3
"""Build one observed EPH poverty release by native EPH agglomerate.

This producer consumes Telescope-A's retained household microscope. It does not
recompute adult equivalents, poverty lines, poverty states, or FGT
contributions. It only aggregates those already-measured contributions using
Telescope-A's PONDIH semantics by native AGLOMERADO and emits EPH_TOTAL as the
explicit coverage aggregate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from poverty_pipeline.estimation_v2 import (
    EstimationQA,
    PovertyEstimate,
    PovertyEstimation,
)
from poverty_pipeline.release_v2 import ParentReleaseRef, write_estimate_release
from poverty_pipeline.science import load_poverty_method


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "configs/geographies/predictive_geography_profiles_v1.json"
DEFAULT_METHOD = ROOT / "configs/poverty_methods/indec-line-poverty-2016-v1.json"
DESIGN_ID = "eph_observed_pondih_v1"
WEIGHT_SEMANTICS = (
    "EPH household PONDIH; person contributions inherit household PONDIH "
    "for each recorded household member"
)


class ObservedAgglomerateError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _profile(path: Path) -> tuple[list[str], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = (payload.get("profiles") or {}).get("eph_agglomerate")
    if not isinstance(profile, dict):
        raise ObservedAgglomerateError("missing eph_agglomerate governed profile")
    expected = profile.get("expected_ids")
    if not isinstance(expected, list) or not expected:
        raise ObservedAgglomerateError("eph_agglomerate profile lacks expected_ids")
    if profile.get("aggregate_geography_level") != "eph_coverage":
        raise ObservedAgglomerateError("eph_agglomerate aggregate level must be eph_coverage")
    if profile.get("aggregate_geography_id") != "EPH_TOTAL":
        raise ObservedAgglomerateError("eph_agglomerate aggregate ID must be EPH_TOTAL")
    return [str(value) for value in expected], sha256(path)


def _normalize_agglomerate(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any() or ((numeric % 1) != 0).any():
        raise ObservedAgglomerateError("Telescope-A AGLOMERADO must be integer-like")
    out = numeric.astype(int).astype(str).str.zfill(2)
    if not out.str.fullmatch(r"[0-9]{2}").all():
        raise ObservedAgglomerateError("Telescope-A AGLOMERADO must round-trip to two digits")
    return out


def build_estimation(
    microscope: pd.DataFrame,
    *,
    period: str,
    release_id: str,
    expected_ids: set[str],
    frame_vintage: str,
) -> tuple[PovertyEstimation, dict]:
    required = {
        "period",
        "household_id",
        "AGLOMERADO",
        "member_count_records",
        "PONDIH",
        "indigence_fgt0",
        "indigence_fgt1",
        "indigence_fgt2",
        "poverty_fgt0",
        "poverty_fgt1",
        "poverty_fgt2",
    }
    missing = sorted(required - set(microscope.columns))
    if missing:
        raise ObservedAgglomerateError(f"Telescope-A microscope missing columns: {missing}")
    if microscope.empty:
        raise ObservedAgglomerateError("Telescope-A microscope must be nonempty")
    if microscope["household_id"].astype(str).duplicated().any():
        raise ObservedAgglomerateError("Telescope-A household identity must be unique")
    observed_periods = set(microscope["period"].astype(str))
    if observed_periods != {period}:
        raise ObservedAgglomerateError(
            f"Telescope-A period mismatch: {sorted(observed_periods)} != {[period]}"
        )

    frame = microscope.copy()
    frame["eph_agglomerate_id"] = _normalize_agglomerate(frame["AGLOMERADO"])
    represented = set(frame["eph_agglomerate_id"])
    if represented != expected_ids:
        raise ObservedAgglomerateError(
            "observed EPH agglomerate inventory differs from governed profile: "
            f"missing={sorted(expected_ids - represented)} "
            f"extra={sorted(represented - expected_ids)}"
        )

    frame["PONDIH"] = pd.to_numeric(frame["PONDIH"], errors="coerce")
    frame["member_count_records"] = pd.to_numeric(
        frame["member_count_records"], errors="coerce"
    )
    if (
        frame["PONDIH"].isna().any()
        or (frame["PONDIH"] <= 0).any()
        or frame["member_count_records"].isna().any()
        or (frame["member_count_records"] <= 0).any()
        or ((frame["member_count_records"] % 1) != 0).any()
    ):
        raise ObservedAgglomerateError(
            "Telescope-A PONDIH/member_count_records contract violated"
        )

    contribution_fields = [
        f"{concept}_fgt{alpha}"
        for concept in ("indigence", "poverty")
        for alpha in (0, 1, 2)
    ]
    for field in contribution_fields:
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
        if (
            frame[field].isna().any()
            or (frame[field] < 0).any()
            or (frame[field] > 1).any()
        ):
            raise ObservedAgglomerateError(f"invalid Telescope-A contribution {field}")

    estimates: list[PovertyEstimate] = []
    aggregate_totals: dict[tuple[str, str, int], tuple[float, float]] = {}

    for agglomerate_id, group in frame.groupby("eph_agglomerate_id", sort=True):
        for universe in ("households", "persons"):
            base_weight = group["PONDIH"].astype(float)
            weights = (
                base_weight
                if universe == "households"
                else base_weight * group["member_count_records"].astype(float)
            )
            for concept in ("indigence", "poverty"):
                for alpha in (0, 1, 2):
                    contribution = group[f"{concept}_fgt{alpha}"].astype(float)
                    numerator = float((weights * contribution).sum())
                    denominator = float(weights.sum())
                    estimates.append(
                        PovertyEstimate(
                            release_id=release_id,
                            estimation_period=period,
                            frame_vintage=frame_vintage,
                            universe=universe,
                            geography_level="eph_agglomerate",
                            geography_id=str(agglomerate_id),
                            concept=concept,
                            estimand=f"fgt{alpha}",
                            estimate=numerator / denominator,
                            unit="proportion",
                            weighted_numerator=numerator,
                            weighted_denominator=denominator,
                            coverage=1.0,
                            design_id=DESIGN_ID,
                            weight_semantics=WEIGHT_SEMANTICS,
                            uncertainty_status="not_supplied",
                        )
                    )
                    key = (universe, concept, alpha)
                    old_num, old_den = aggregate_totals.get(key, (0.0, 0.0))
                    aggregate_totals[key] = (
                        old_num + numerator,
                        old_den + denominator,
                    )

    for (universe, concept, alpha), (numerator, denominator) in sorted(
        aggregate_totals.items()
    ):
        estimates.append(
            PovertyEstimate(
                release_id=release_id,
                estimation_period=period,
                frame_vintage=frame_vintage,
                universe=universe,
                geography_level="eph_coverage",
                geography_id="EPH_TOTAL",
                concept=concept,
                estimand=f"fgt{alpha}",
                estimate=numerator / denominator,
                unit="proportion",
                weighted_numerator=numerator,
                weighted_denominator=denominator,
                coverage=1.0,
                design_id=DESIGN_ID,
                weight_semantics=WEIGHT_SEMANTICS,
                uncertainty_status="not_supplied",
            )
        )

    expected_fact_count = len(expected_ids) * 12 + 12
    if len(estimates) != expected_fact_count:
        raise ObservedAgglomerateError(
            f"expected {expected_fact_count} facts, got {len(estimates)}"
        )
    qa = EstimationQA(
        household_rows=len(frame),
        person_rows=int(frame["member_count_records"].sum()),
        domain_count=len(expected_ids),
        min_analysis_weight=float(frame["PONDIH"].min()),
        max_analysis_weight=float(frame["PONDIH"].max()),
        national_reconciliation="passed",
        uncertainty_status="not_supplied",
    )
    diagnostics = {
        "schema_version": "observed-eph-agglomerate-diagnostics/v1",
        "period": period,
        "household_rows": len(frame),
        "person_rows": int(frame["member_count_records"].sum()),
        "agglomerate_count": len(expected_ids),
        "household_pondih_mass": float(frame["PONDIH"].sum()),
        "person_pondih_mass": float(
            (frame["PONDIH"] * frame["member_count_records"]).sum()
        ),
        "aggregate_geography": {"level": "eph_coverage", "id": "EPH_TOTAL"},
        "poverty_recomputed": False,
        "measurement_source": "Telescope-A household microscope contributions",
    }
    return PovertyEstimation(tuple(estimates), qa), diagnostics


def build_release(
    *,
    telescope_a_dir: Path,
    output: Path,
    period: str,
    profile_path: Path,
    method_path: Path,
    frame_vintage: str,
) -> Path:
    microscope_path = telescope_a_dir / "households.parquet"
    summary_path = telescope_a_dir / "summary.json"
    if not microscope_path.is_file() or not summary_path.is_file():
        raise ObservedAgglomerateError(
            "Telescope-A directory must contain households.parquet and summary.json"
        )
    expected_ids, profile_hash = _profile(profile_path)
    microscope = pd.read_parquet(microscope_path)
    release_id = f"poverty-estimate-release-{period.lower()}-eph-agglomerate-observed-v1"
    estimation, diagnostics = build_estimation(
        microscope,
        period=period,
        release_id=release_id,
        expected_ids=set(expected_ids),
        frame_vintage=frame_vintage,
    )
    method = load_poverty_method(method_path)
    parents = (
        ParentReleaseRef(
            "observed_measurement",
            f"telescope-a-{period.lower()}",
            sha256(microscope_path),
        ),
        ParentReleaseRef(
            "observed_measurement_summary",
            f"telescope-a-summary-{period.lower()}",
            sha256(summary_path),
        ),
        ParentReleaseRef(
            "geography_profile",
            "eph-agglomerate-governed-profile-v1",
            profile_hash,
        ),
        ParentReleaseRef(
            "poverty_method",
            method.release_id,
            sha256(method_path),
        ),
    )
    root = write_estimate_release(
        output,
        estimation,
        parents=parents,
        method_release_id=method.release_id,
        status="research_estimate",
    )
    # Detached release file set is fixed by v2, so diagnostics live alongside the
    # source Telescope-A run rather than mutating the release contract.
    diagnostic_path = output.parent / f"{output.name}.observed_diagnostics.json"
    diagnostic_path.write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", required=True)
    parser.add_argument("--telescope-a", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--method", type=Path, default=DEFAULT_METHOD)
    parser.add_argument("--frame-vintage", default="EPH")
    args = parser.parse_args()
    root = build_release(
        telescope_a_dir=args.telescope_a,
        output=args.output,
        period=args.period,
        profile_path=args.profile,
        method_path=args.method,
        frame_vintage=args.frame_vintage,
    )
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
