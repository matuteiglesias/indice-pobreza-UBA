#!/usr/bin/env python3
"""Run the governed eight-period predictive poverty batch from resolved parent refs.

The committed batch spec contains logical refs only.  A separate resolution file
supplies local/fixture paths plus hashes; it is intentionally not committed by
this runner.  Every declared parent is hash-verified before computation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from poverty_pipeline.release_v2 import verify_estimate_release

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_SPEC = ROOT / "configs/releases/predictive-poverty-2024q1-2025q4.json"
DEFAULT_PROFILE = ROOT / "configs/geographies/predictive_geography_profiles_v1.json"
_GEOGRAPHY_SPEC = importlib.util.spec_from_file_location(
    "predictive_geography_release",
    SCRIPT_DIR / "build_predictive_geography_release.py",
)
_GEOGRAPHY_MODULE = importlib.util.module_from_spec(_GEOGRAPHY_SPEC)
assert _GEOGRAPHY_SPEC and _GEOGRAPHY_SPEC.loader
_GEOGRAPHY_SPEC.loader.exec_module(_GEOGRAPHY_MODULE)

_RECONCILE_SPEC = importlib.util.spec_from_file_location(
    "reconcile_predictive_geographies",
    SCRIPT_DIR / "reconcile_predictive_geographies.py",
)
_RECONCILE_MODULE = importlib.util.module_from_spec(_RECONCILE_SPEC)
assert _RECONCILE_SPEC and _RECONCILE_SPEC.loader
_RECONCILE_SPEC.loader.exec_module(_RECONCILE_MODULE)

build_release = _GEOGRAPHY_MODULE.build_release
load_profiles = _GEOGRAPHY_MODULE.load_profiles
reconcile_releases = _RECONCILE_MODULE.reconcile_releases


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_batch_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "predictive-poverty-batch/v1":
        raise ValueError("unsupported predictive poverty batch schema")
    if spec.get("geography_level") != "department_2010":
        raise ValueError("commissioning batch must target department_2010")
    rows = spec.get("periods")
    if not isinstance(rows, list):
        raise ValueError("batch periods must be an array")
    if not rows:
        raise ValueError("batch periods must be nonempty")
    periods = tuple(str(row.get("period")) for row in rows)
    if len(periods) != len(set(periods)):
        raise ValueError("batch periods must be unique")
    pattern = re.compile(r"^(20\\d{2})-Q([1-4])$")
    parsed: list[tuple[int, int]] = []
    for period in periods:
        match = pattern.fullmatch(period)
        if match is None:
            raise ValueError(f"invalid batch period: {period!r}")
        parsed.append((int(match.group(1)), int(match.group(2))))
    if parsed != sorted(parsed):
        raise ValueError("batch periods must be in chronological order")
    ordinal = [year * 4 + quarter for year, quarter in parsed]
    if any(right != left + 1 for left, right in zip(ordinal, ordinal[1:])):
        raise ValueError("batch periods must form one contiguous quarterly envelope")
    required_refs = (
        "census_sample_release_ref",
        "frame_ref",
        "semantic_plane_release_ref",
        "predictive_welfare_release_ref",
        "basket_slice_ref",
    )
    for row in rows:
        period = str(row["period"])
        target_year = int(row["target_year"])
        if target_year != int(period[:4]):
            raise ValueError(f"target_year mismatch for {period}")
        for field in required_refs:
            value = row.get(field)
            if not isinstance(value, str) or not value or value.startswith("/"):
                raise ValueError(f"{period} requires a logical non-absolute {field}")
    by_year: dict[int, set[str]] = {}
    for row in rows:
        by_year.setdefault(int(row["target_year"]), set()).add(
            str(row["census_sample_release_ref"])
        )
    if any(len(refs) != 1 for refs in by_year.values()):
        raise ValueError("the four quarters of each target year must reuse one Census sample ref")


def _hash_target(path: Path) -> Path:
    if path.is_file():
        return path
    manifest = path / "manifest.json"
    if not manifest.is_file():
        raise ValueError(f"resolved directory requires manifest.json for custody: {path}")
    return manifest


def verify_resolution(ref: str, resolutions: dict[str, Any]) -> dict[str, str]:
    record = resolutions.get(ref)
    if not isinstance(record, dict):
        raise ValueError(f"unresolved parent ref: {ref}")
    raw_path = record.get("path")
    digest = record.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"resolved parent {ref} requires path")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"resolved parent {ref} requires sha256")
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"resolved parent path does not exist: {ref}: {path}")
    hash_target = _hash_target(path)
    observed = sha256(hash_target)
    if observed != digest:
        raise ValueError(
            f"resolved parent hash mismatch: {ref}: expected {digest}, got {observed}"
        )
    return {
        "ref": ref,
        "path": str(path),
        "hash_target": str(hash_target),
        "sha256": observed,
    }


def _fact_counts(release: Path, level: str) -> tuple[int, int, int, int]:
    with (release / "poverty_estimates.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    geography_ids = {
        row["geography_id"] for row in rows if row["geography_level"] == level
    }
    spatial = sum(row["geography_level"] == level for row in rows)
    national = sum(row["geography_level"] == "national" for row in rows)
    return len(geography_ids), spatial, national, len(rows)


def run_batch(
    *,
    spec_path: Path,
    resolved_parents_path: Path,
    output: Path,
    profile_path: Path = DEFAULT_PROFILE,
    method_path: Path | None = None,
) -> Path:
    spec = _read_json(spec_path)
    validate_batch_spec(spec)
    resolved_payload = _read_json(resolved_parents_path)
    if resolved_payload.get("schema_version") != "predictive-poverty-parent-resolution/v1":
        raise ValueError("unsupported parent-resolution schema")
    resolutions = resolved_payload.get("refs")
    if not isinstance(resolutions, dict):
        raise ValueError("parent-resolution refs must be an object")

    profiles = load_profiles(profile_path)
    expected_departments = len(profiles["department_2010"]["expected_ids"])
    expected_provinces = len(profiles["province_2010"]["expected_ids"])
    method = method_path or ROOT / "configs/poverty_methods/indec-line-poverty-2016-v1.json"

    output.mkdir(parents=True, exist_ok=True)
    releases_root = output / "releases"
    oracles_root = output / "province-oracles"
    reconciliation_root = output / "reconciliation"
    period_entries: list[dict[str, Any]] = []
    parent_report: dict[str, Any] = {
        "schema_version": "predictive-poverty-parent-resolution-report/v1",
        "periods": {},
    }
    reconciliation_reports: list[dict[str, Any]] = []

    for row in spec["periods"]:
        period = str(row["period"])
        resolved = {
            field: verify_resolution(str(row[field]), resolutions)
            for field in (
                "census_sample_release_ref",
                "frame_ref",
                "semantic_plane_release_ref",
                "predictive_welfare_release_ref",
                "basket_slice_ref",
            )
        }
        parent_report["periods"][period] = resolved

        frame_path = Path(resolved["frame_ref"]["path"])
        welfare_path = Path(resolved["predictive_welfare_release_ref"]["path"])
        baskets_path = Path(resolved["basket_slice_ref"]["path"])

        department_output = releases_root / period
        province_output = oracles_root / period
        build_release(
            welfare_path=welfare_path,
            frame_path=frame_path,
            baskets_path=baskets_path,
            method_path=method,
            output=department_output,
            period=period,
            geography_level="department_2010",
            profile_path=profile_path,
        )
        verify_estimate_release(department_output)
        build_release(
            welfare_path=welfare_path,
            frame_path=frame_path,
            baskets_path=baskets_path,
            method_path=method,
            output=province_output,
            period=period,
            geography_level="province_2010",
            profile_path=profile_path,
        )
        verify_estimate_release(province_output)

        geography_count, spatial_facts, national_facts, total_facts = _fact_counts(
            department_output, "department_2010"
        )
        if geography_count != expected_departments:
            raise ValueError(
                f"{period}: expected {expected_departments} departments, got {geography_count}"
            )
        if spatial_facts != expected_departments * 12 or national_facts != 12:
            raise ValueError(f"{period}: unexpected department/national fact cardinality")
        province_count, _, _, _ = _fact_counts(province_output, "province_2010")
        if province_count != expected_provinces:
            raise ValueError(
                f"{period}: expected {expected_provinces} provinces, got {province_count}"
            )

        reconciliation = reconcile_releases(department_output, province_output)
        reconciliation_reports.append(reconciliation)
        reconciliation_root.mkdir(parents=True, exist_ok=True)
        (reconciliation_root / f"{period}.json").write_text(
            json.dumps(reconciliation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if reconciliation["status"] != "PASS":
            raise ValueError(f"{period}: department reconciliation failed")

        manifest_path = department_output / "release_manifest.json"
        manifest = _read_json(manifest_path)
        period_entries.append(
            {
                "period": period,
                "target_year": int(row["target_year"]),
                "release_id": manifest["release_id"],
                "release_manifest_sha256": sha256(manifest_path),
                "geography_count": geography_count,
                "department_fact_count": spatial_facts,
                "national_fact_count": national_facts,
                "fact_count": total_facts,
                "reconciliation_status": reconciliation["status"],
            }
        )

    batch_manifest = {
        "schema_version": "department-poverty-batch/v1",
        "batch_id": spec["batch_id"],
        "geography_level": "department_2010",
        "periods": period_entries,
        "all_period_qa": {
            "period_count": len(period_entries),
            "geography_count_each": expected_departments,
            "department_fact_count": sum(
                item["department_fact_count"] for item in period_entries
            ),
            "national_fact_count": sum(
                item["national_fact_count"] for item in period_entries
            ),
            "fact_count": sum(item["fact_count"] for item in period_entries),
            "reconciliation_status": (
                "PASS"
                if all(item["reconciliation_status"] == "PASS" for item in period_entries)
                else "FAIL"
            ),
        },
    }
    batch_path = output / "batch_manifest.json"
    parents_path = output / "parent_resolution_report.json"
    reconciliations_path = output / "reconciliation_report.json"
    batch_path.write_text(
        json.dumps(batch_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    parents_path.write_text(
        json.dumps(parent_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    reconciliations_path.write_text(
        json.dumps(
            {
                "schema_version": "predictive-poverty-reconciliation-set/v1",
                "reports": reconciliation_reports,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "checksums.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in (batch_path, parents_path, reconciliations_path)
        ),
        encoding="utf-8",
    )
    return batch_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--resolved-parents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--method", type=Path)
    args = parser.parse_args()
    batch_path = run_batch(
        spec_path=args.spec,
        resolved_parents_path=args.resolved_parents,
        output=args.output,
        profile_path=args.profile,
        method_path=args.method,
    )
    print(batch_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
