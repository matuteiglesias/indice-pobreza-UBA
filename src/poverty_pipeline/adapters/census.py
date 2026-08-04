"""Strict Census person/household adapter (no sampling or ID generation)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

from poverty_pipeline.contracts import ContractError, ValidatedRelease, validate_release

PERSON_COLUMNS = ("sample_person_id", "sample_household_id", "sex_code", "age_years", "radio_2010_id", "sample_weight")
HOUSEHOLD_COLUMNS = ("sample_household_id", "department_2010_id", "region_id")


def _read_csv(path: Path, required: tuple[str, ...], allowed_extra: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        missing = set(required) - set(columns)
        unexpected = set(columns) - set(required) - set(allowed_extra)
        if missing or unexpected:
            raise ContractError(f"table schema mismatch; missing={sorted(missing)}, unexpected={sorted(unexpected)}")
        return list(reader)


def _output_hash(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def adapt_census(release_or_path: ValidatedRelease | str | Path) -> tuple[list[dict], list[dict], dict]:
    release = release_or_path if isinstance(release_or_path, ValidatedRelease) else validate_release(
        release_or_path, expected_artifact_type="research.census-sample/v1"
    )
    compatibility = release.manifest["compatibility"]
    extras = compatibility.get("allowed_provenance_columns", [])
    if not isinstance(extras, list) or not all(isinstance(v, str) for v in extras):
        raise ContractError("allowed provenance columns must be an explicit string list")
    persons = _read_csv(release.role_path("census_persons"), PERSON_COLUMNS, extras)
    households = _read_csv(release.role_path("census_households"), HOUSEHOLD_COLUMNS, extras)
    person_ids = [row["sample_person_id"] for row in persons]
    household_ids = [row["sample_household_id"] for row in households]
    if any(not value for value in person_ids + household_ids):
        raise ContractError("IDs must be nonempty strings supplied by the producer")
    if len(person_ids) != len(set(person_ids)):
        raise ContractError("duplicate sample_person_id")
    if len(household_ids) != len(set(household_ids)):
        raise ContractError("duplicate sample_household_id")
    household_set = set(household_ids)
    orphans = sorted({row["sample_household_id"] for row in persons} - household_set)
    if orphans:
        raise ContractError(f"orphan person household references: {orphans}")
    for row in persons:
        try:
            weight = float(row["sample_weight"])
        except ValueError as exc:
            raise ContractError("sample weights must be finite and positive") from exc
        if not math.isfinite(weight) or weight <= 0:
            raise ContractError("sample weights must be finite and positive")
        row["sample_weight"] = weight
        try:
            row["age_years"] = int(row["age_years"])
        except ValueError as exc:
            raise ContractError("age_years must be an integer") from exc
    for row in households:
        if not row["department_2010_id"] or not row["region_id"]:
            raise ContractError("each household requires one declared department and region")
    persons.sort(key=lambda row: row["sample_person_id"])
    households.sort(key=lambda row: row["sample_household_id"])
    qa = {
        "release_id": release.manifest["release_id"], "manifest_sha256": release.manifest_hash,
        "input_row_counts": {"persons": len(persons), "households": len(households)},
        "key_uniqueness": {"persons": True, "households": True}, "foreign_key_coverage": 1.0,
        "sample_id_namespace": compatibility["sample_id_namespace"],
        "period": release.manifest["period"],
        "geography_coverage": sum(bool(r["department_2010_id"]) for r in households),
        "region_coverage": sum(bool(r["region_id"]) for r in households),
        "output_row_counts": {"persons": len(persons), "households": len(households)},
        "output_hashes": {"persons": _output_hash(persons), "households": _output_hash(households)},
        "scientific_execution_performed": False,
    }
    return persons, households, qa
