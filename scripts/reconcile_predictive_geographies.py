#!/usr/bin/env python3
"""Reconcile detached department poverty facts to province and national oracles."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

TOLERANCE = 1e-12
CUBE_FIELDS = ("estimation_period", "universe", "concept", "estimand")


def _read_rows(release: Path) -> list[dict[str, str]]:
    path = release / "poverty_estimates.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(row: dict[str, str], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"non-finite {field}")
    return value


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=TOLERANCE, abs_tol=TOLERANCE)


def reconcile_releases(
    department_release: Path,
    province_release: Path,
) -> dict[str, Any]:
    departments = _read_rows(department_release)
    provinces = _read_rows(province_release)

    department_levels = {row["geography_level"] for row in departments}
    province_levels = {row["geography_level"] for row in provinces}
    if department_levels != {"department_2010", "national"}:
        raise ValueError(f"unexpected department release levels: {sorted(department_levels)}")
    if province_levels != {"province_2010", "national"}:
        raise ValueError(f"unexpected province release levels: {sorted(province_levels)}")

    period = {row["estimation_period"] for row in departments}
    province_period = {row["estimation_period"] for row in provinces}
    if len(period) != 1 or period != province_period:
        raise ValueError("department and province releases must share one period")

    province_index = {
        (*[row[field] for field in CUBE_FIELDS], row["geography_id"]): row
        for row in provinces
        if row["geography_level"] == "province_2010"
    }
    national_index = {
        tuple(row[field] for field in CUBE_FIELDS): row
        for row in provinces
        if row["geography_level"] == "national"
    }

    grouped: dict[tuple[str, ...], list[float]] = {}
    national_from_departments: dict[tuple[str, ...], list[float]] = {}
    for row in departments:
        if row["geography_level"] != "department_2010":
            continue
        department_id = row["geography_id"]
        if len(department_id) != 5 or not department_id.isdigit():
            raise ValueError(f"invalid department ID in reconciliation: {department_id!r}")
        cube = tuple(row[field] for field in CUBE_FIELDS)
        key = (*cube, department_id[:2])
        cell = grouped.setdefault(key, [0.0, 0.0])
        cell[0] += _number(row, "weighted_numerator")
        cell[1] += _number(row, "weighted_denominator")
        national = national_from_departments.setdefault(cube, [0.0, 0.0])
        national[0] += _number(row, "weighted_numerator")
        national[1] += _number(row, "weighted_denominator")

    failures: list[dict[str, Any]] = []
    checked_province_cells = 0
    for key, (numerator, denominator) in sorted(grouped.items()):
        oracle = province_index.get(key)
        if oracle is None:
            failures.append({"kind": "missing_province_oracle", "key": list(key)})
            continue
        oracle_n = _number(oracle, "weighted_numerator")
        oracle_d = _number(oracle, "weighted_denominator")
        oracle_estimate = _number(oracle, "estimate")
        estimate = numerator / denominator
        checked_province_cells += 1
        if not (_close(numerator, oracle_n) and _close(denominator, oracle_d) and _close(estimate, oracle_estimate)):
            failures.append(
                {
                    "kind": "department_to_province_mismatch",
                    "key": list(key),
                    "department_numerator": numerator,
                    "province_numerator": oracle_n,
                    "department_denominator": denominator,
                    "province_denominator": oracle_d,
                    "department_estimate": estimate,
                    "province_estimate": oracle_estimate,
                }
            )

    checked_national_cells = 0
    for cube, (numerator, denominator) in sorted(national_from_departments.items()):
        oracle = national_index.get(cube)
        if oracle is None:
            failures.append({"kind": "missing_national_oracle", "key": list(cube)})
            continue
        oracle_n = _number(oracle, "weighted_numerator")
        oracle_d = _number(oracle, "weighted_denominator")
        oracle_estimate = _number(oracle, "estimate")
        estimate = numerator / denominator
        checked_national_cells += 1
        if not (_close(numerator, oracle_n) and _close(denominator, oracle_d) and _close(estimate, oracle_estimate)):
            failures.append(
                {
                    "kind": "department_to_national_mismatch",
                    "key": list(cube),
                    "department_numerator": numerator,
                    "national_numerator": oracle_n,
                    "department_denominator": denominator,
                    "national_denominator": oracle_d,
                    "department_estimate": estimate,
                    "national_estimate": oracle_estimate,
                }
            )

    return {
        "schema_version": "predictive-poverty-reconciliation/v1",
        "period": next(iter(period)),
        "tolerance": TOLERANCE,
        "checked_province_cells": checked_province_cells,
        "checked_national_cells": checked_national_cells,
        "failure_count": len(failures),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--department-release", type=Path, required=True)
    parser.add_argument("--province-release", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = reconcile_releases(args.department_release, args.province_release)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
