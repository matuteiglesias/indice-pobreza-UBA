#!/usr/bin/env python3
"""Build one bounded predictive poverty release for a governed geography profile.

This producer changes only the grouping/domain identity relative to the accepted
predictive province path.  It does not train or transform welfare, alter the
poverty method, manufacture weights, load geometry, or aggregate in a consumer.

Production CLI runs accept only versioned profiles from
``configs/geographies/predictive_geography_profiles_v1.json``.  Tests may pass
an explicit expected-ID override to exercise small synthetic inventories.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    HouseholdDomain,
    HouseholdWeight,
)
from poverty_pipeline.predictive_estimation_v2 import estimate_predictive_poverty
from poverty_pipeline.release_v2 import ParentReleaseRef, write_estimate_release
from poverty_pipeline.science import load_poverty_method
from poverty_pipeline.science.measurement import HouseholdPovertyLines, PersonMember
from poverty_pipeline.science.predictive_measurement import (
    EmpiricalResidualDistribution,
    PredictiveHouseholdWelfare,
    measure_predictive_poverty,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT / "configs/geographies/predictive_geography_profiles_v1.json"
FRAME_VINTAGE = "2010"
DESIGN_ID = "unit_weight_target_year_sample_research_v1"
WEIGHT_SEMANTICS = "unit_analysis_weight"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def content_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = value.get("rows", value.get("households", value.get("persons")))
        if not isinstance(value, list):
            raise ValueError(f"expected a JSON array of rows: {path}")
        return value
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_table(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".json", ".csv"}:
        return _read_rows(path)
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - local real-data path
        raise RuntimeError("Parquet welfare input requires pyarrow") from exc
    return pq.read_table(path).to_pylist()


def _num(row: dict[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field {key!r}") from exc
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"non-finite numeric field {key!r}")
    return value


def load_profiles(path: Path = DEFAULT_PROFILE_PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "poverty-geography-profiles/v1":
        raise ValueError("unsupported predictive geography profile schema")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("predictive geography profiles must be nonempty")
    for level, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"invalid geography profile: {level}")
        expected = profile.get("expected_ids")
        if not isinstance(expected, list) or not expected or len(expected) != len(set(expected)):
            raise ValueError(f"profile {level} requires unique expected_ids")
        pattern = re.compile(str(profile.get("id_regex", "")))
        if not all(isinstance(value, str) and pattern.fullmatch(value) for value in expected):
            raise ValueError(f"profile {level} expected_ids violate id_regex")
        if not isinstance(profile.get("field"), str) or not profile["field"]:
            raise ValueError(f"profile {level} requires a frame field")
    return profiles


def _load_frame(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("households"), list)
        or not isinstance(payload.get("persons"), list)
    ):
        raise ValueError("frame JSON must contain households and persons arrays")
    households = payload["households"]
    persons = payload["persons"]
    household_ids = [str(row.get("household_id", "")) for row in households]
    person_ids = [str(row.get("person_id", "")) for row in persons]
    if not all(household_ids) or len(set(household_ids)) != len(household_ids):
        raise ValueError("frame household IDs must be nonempty and unique")
    if not all(person_ids) or len(set(person_ids)) != len(person_ids):
        raise ValueError("frame person IDs must be nonempty and unique")
    return households, persons, payload


def _load_baskets(path: Path, basket_period: str) -> dict[str, tuple[float, float]]:
    rows = _read_rows(path)
    result: dict[str, tuple[float | None, float | None]] = {}
    for row in rows:
        row_period = str(row.get("period", row.get("date", row.get("Fecha", row.get("Q", "")))))
        if row_period != basket_period:
            continue
        region = (
            str(row.get("region_id", row.get("region", row.get("Region", ""))))
            .strip()
            .lower()
            .replace(" ", "_")
        )
        if not region:
            raise ValueError("basket row has no region_id")
        if "measure" in row:
            measure = str(row["measure"]).upper()
            if measure not in {"CBA", "CBT"}:
                raise ValueError(f"unsupported basket measure {measure!r}")
            value = _num(row, "value_2016_01")
            current = list(result.get(region, (None, None)))
            current[0 if measure == "CBA" else 1] = value
            result[region] = (current[0], current[1])
        else:
            result[region] = (
                _num(row, "CBA_2016_01" if "CBA_2016_01" in row else "CBA"),
                _num(row, "CBT_2016_01" if "CBT_2016_01" in row else "CBT"),
            )
    required = {"cuyo", "gran_buenos_aires", "noreste", "noroeste", "pampeana", "patagonia"}
    if set(result) != required or any(cba is None or cbt is None for cba, cbt in result.values()):
        raise ValueError(
            f"basket slice {basket_period!r} must contain exactly six complete regions; "
            f"got {sorted(result)}"
        )
    return {region: (float(cba), float(cbt)) for region, (cba, cbt) in result.items()}


def _load_welfare(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if path.is_dir():
        locations = path / "household_locations.parquet"
        residuals = path / "residual_ecdf.parquet"
        manifest_path = path / "manifest.json"
        if not locations.exists() or not residuals.exists() or not manifest_path.exists():
            raise ValueError(
                "welfare release must contain household_locations.parquet, "
                "residual_ecdf.parquet, manifest.json"
            )
        checks_path = path / "checksums.sha256"
        if checks_path.exists():
            for line in checks_path.read_text(encoding="utf-8").splitlines():
                digest, name = line.split("  ", 1)
                if sha256(path / name) != digest:
                    raise ValueError(f"welfare input checksum mismatch: {name}")
        households = _read_table(locations)
        residual_rows = _read_table(residuals)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("artifact_type") != "research.household-welfare-predictive/v1":
            raise ValueError("unsupported predictive welfare artifact type")
        if manifest.get("support_policy") != "floor_at_zero":
            raise ValueError("unsupported predictive welfare support policy")
        return households, residual_rows, manifest
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("welfare JSON must be an object")
    return payload["households"], payload["residuals"], payload.get("manifest", {})


def _release_id(period: str, geography_level: str) -> str:
    level_slug = geography_level.removesuffix("_2010").replace("_", "-")
    return f"poverty-estimate-release-{period.lower()}-{level_slug}-predictive-v1"


def _geography_id(row: dict[str, Any], *, field: str, pattern: re.Pattern[str]) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be a zero-preserving string; numeric geography coercion is forbidden"
        )
    if not pattern.fullmatch(value):
        raise ValueError(f"{field} violates governed ID format: {value!r}")
    return value


def build_release(
    *,
    welfare_path: Path,
    frame_path: Path,
    baskets_path: Path,
    method_path: Path,
    output: Path,
    period: str,
    geography_level: str,
    basket_period: str | None = None,
    frame_vintage: str = FRAME_VINTAGE,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    expected_geography_ids: set[str] | None = None,
    expected_households: int | None = None,
    expected_persons: int | None = None,
) -> Path:
    profiles = load_profiles(profile_path)
    if geography_level not in profiles:
        raise ValueError(f"unsupported governed geography level: {geography_level}")
    profile = profiles[geography_level]
    geography_field = str(profile["field"])
    id_pattern = re.compile(str(profile["id_regex"]))
    governed_ids = set(profile["expected_ids"]) if expected_geography_ids is None else set(expected_geography_ids)
    if not governed_ids:
        raise ValueError("expected geography inventory must be nonempty")
    if not all(id_pattern.fullmatch(value) for value in governed_ids):
        raise ValueError("expected geography inventory violates governed profile")

    households, persons, frame_manifest = _load_frame(frame_path)
    welfare_rows, residual_rows, welfare_manifest = _load_welfare(welfare_path)
    baskets = _load_baskets(baskets_path, basket_period or period)
    method = load_poverty_method(method_path)

    household_by_id = {str(row["household_id"]): row for row in households}
    welfare_ids = [str(row.get("household_id", "")) for row in welfare_rows]
    if not all(welfare_ids) or len(set(welfare_ids)) != len(welfare_ids):
        raise ValueError("welfare household IDs must be nonempty and unique")
    welfare_by_id = {str(row["household_id"]): row for row in welfare_rows}
    if set(welfare_by_id) != set(household_by_id):
        raise ValueError("welfare households must exactly match frame households")
    if expected_households is not None and len(households) != expected_households:
        raise ValueError(f"expected {expected_households} households, got {len(households)}")
    if expected_persons is not None and len(persons) != expected_persons:
        raise ValueError(f"expected {expected_persons} persons, got {len(persons)}")

    frame_persons: list[PersonMember] = []
    for row in persons:
        household_id = str(row["household_id"])
        if household_id not in household_by_id:
            raise ValueError(f"person references unknown household: {household_id}")
        frame_persons.append(
            PersonMember(str(row["person_id"]), household_id, str(row["sex"]), int(row["age"]))
        )

    lines: list[HouseholdPovertyLines] = []
    domains: list[HouseholdDomain] = []
    weights: list[HouseholdWeight] = []
    for household_id, row in sorted(household_by_id.items()):
        region = str(row["region_id"]).strip().lower().replace(" ", "_")
        if region not in baskets:
            raise ValueError(f"household {household_id} has unknown basket region {region!r}")
        cba, cbt = baskets[region]
        lines.append(HouseholdPovertyLines(household_id, cba, cbt))
        geography_id = _geography_id(row, field=geography_field, pattern=id_pattern)
        domains.append(HouseholdDomain(household_id, geography_level, geography_id))
        analysis_weight = _num(row, "analysis_weight")
        if analysis_weight != 1.0:
            raise ValueError("this producer accepts only unit analysis weights")
        weights.append(HouseholdWeight(household_id, analysis_weight))

    represented_ids = {domain.geography_id for domain in domains}
    if represented_ids != governed_ids:
        missing = sorted(governed_ids - represented_ids)
        extra = sorted(represented_ids - governed_ids)
        raise ValueError(
            f"{geography_level} IDs do not equal governed inventory: "
            f"missing={missing[:20]} extra={extra[:20]}"
        )

    welfare = tuple(
        PredictiveHouseholdWelfare(
            household_id,
            _num(row, "point_welfare"),
            str(row.get("estimation_status", "estimated")),
        )
        for household_id, row in sorted(welfare_by_id.items())
    )
    residuals = tuple(_num(row, "residual") for row in residual_rows)
    measurement = measure_predictive_poverty(
        frame_persons,
        welfare,
        lines,
        method,
        EmpiricalResidualDistribution(residuals, support_policy="floor_at_zero"),
    )
    design = EstimationDesign(DESIGN_ID, WEIGHT_SEMANTICS, tuple(weights))
    release_id = _release_id(period, geography_level)
    estimation = estimate_predictive_poverty(
        measurement,
        domains,
        design,
        EstimationContext(release_id, period, frame_vintage),
    )
    expected_facts = len(governed_ids) * 12 + 12
    if len(estimation.estimates) != expected_facts:
        raise ValueError(f"expected {expected_facts} facts, got {len(estimation.estimates)}")

    method_hash = sha256(method_path)
    frame_hash = sha256(frame_path)
    basket_hash = sha256(baskets_path)
    welfare_hash = (
        sha256(welfare_path / "manifest.json") if welfare_path.is_dir() else sha256(welfare_path)
    )
    parents = (
        ParentReleaseRef(
            "population_frame",
            str(frame_manifest.get("release_id", "population-frame")),
            frame_hash,
        ),
        ParentReleaseRef(
            "welfare",
            str(welfare_manifest.get("release_id", "predictive-welfare")),
            welfare_hash,
        ),
        ParentReleaseRef("poverty_lines", f"basket-slice-{basket_period or period}", basket_hash),
        ParentReleaseRef(
            "threshold_area_binding",
            f"{geography_level}-region-binding-{period}",
            content_hash(sorted((household_id, row["region_id"]) for household_id, row in household_by_id.items())),
        ),
        ParentReleaseRef("poverty_method", method.release_id, method_hash),
    )
    return write_estimate_release(
        output,
        estimation,
        parents=parents,
        method_release_id=method.release_id,
        status="research_estimate",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", required=True)
    parser.add_argument("--geography-level", required=True)
    parser.add_argument("--welfare-release", type=Path, required=True)
    parser.add_argument("--frame", type=Path, required=True, help="JSON population frame handoff")
    parser.add_argument("--baskets", type=Path, required=True)
    parser.add_argument("--basket-period")
    parser.add_argument(
        "--method",
        type=Path,
        default=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--frame-vintage", default=FRAME_VINTAGE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-households", type=int)
    parser.add_argument("--expected-persons", type=int)
    args = parser.parse_args()
    root = build_release(
        welfare_path=args.welfare_release,
        frame_path=args.frame,
        baskets_path=args.baskets,
        method_path=args.method,
        output=args.output,
        period=args.period,
        geography_level=args.geography_level,
        basket_period=args.basket_period,
        frame_vintage=args.frame_vintage,
        profile_path=args.profile,
        expected_households=args.expected_households,
        expected_persons=args.expected_persons,
    )
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
