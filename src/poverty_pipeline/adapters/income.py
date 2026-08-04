"""Exact-ID person-income adapter and explicit mechanical transforms."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

from poverty_pipeline.contracts import ALLOWED_TRANSFORMS, ContractError, ValidatedRelease, validate_release

INCOME_COLUMNS = ("sample_person_id", "period", "prediction_value", "prediction_transform", "monetary_reference", "classification", "model_release_id")
CLASSIFICATIONS = {"observed", "derived", "projected", "synthetic"}


def to_linear_ars(value: float, source_transform: str) -> float:
    """Mechanically invert one declared transform; this is not an unbiased expectation."""
    try:
        if source_transform == "linear_ars":
            result = value
        elif source_transform == "log10_ars":
            result = 10.0 ** value
        elif source_transform == "log10_ars_plus_1":
            result = 10.0 ** value - 1.0
        else:
            raise ContractError(f"unknown prediction transform: {source_transform}")
    except OverflowError as exc:
        raise ContractError("converted income must be finite and nonnegative; clipping is forbidden") from exc
    if not math.isfinite(result) or result < 0:
        raise ContractError("converted income must be finite and nonnegative; clipping is forbidden")
    return result


def adapt_income(
    release_or_path: ValidatedRelease | str | Path,
    census_persons: list[dict], *, selected_period: str, sample_id_namespace: str,
    requested_output_transform: str = "linear_ars",
) -> tuple[list[dict], dict]:
    release = release_or_path if isinstance(release_or_path, ValidatedRelease) else validate_release(
        release_or_path, expected_artifact_type="research.person-income-predictions/v1"
    )
    compatibility = release.manifest["compatibility"]
    if compatibility.get("sample_id_namespace") != sample_id_namespace:
        raise ContractError("sample-ID namespace mismatch")
    source_transform = compatibility.get("prediction_transform")
    if source_transform not in ALLOWED_TRANSFORMS:
        raise ContractError("manifest declares an unknown prediction transform")
    if requested_output_transform != "linear_ars":
        raise ContractError("sprint-zero adapter only converts explicitly to linear_ars")
    if release.manifest["period"] != selected_period:
        raise ContractError("income release period mismatch")
    with release.role_path("person_income_predictions").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != INCOME_COLUMNS:
            raise ContractError("income table schema or column order mismatch")
        rows = list(reader)
    census_id_list = [str(row["sample_person_id"]) for row in census_persons]
    if len(census_id_list) != len(set(census_id_list)):
        raise ContractError("multiplied Census sample_person_id")
    census_ids = set(census_id_list)
    keys = [(row["sample_person_id"], row["period"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ContractError("duplicate person-period prediction key")
    for row in rows:
        if row["period"] != selected_period:
            raise ContractError("prediction row period mismatch")
        if row["prediction_transform"] != source_transform:
            raise ContractError("row/manifest transform disagreement or double-transform attempt")
        if row["monetary_reference"] != compatibility.get("monetary_reference"):
            raise ContractError("row/manifest monetary reference disagreement")
        if row["classification"] not in CLASSIFICATIONS:
            raise ContractError("unknown prediction classification")
    prediction_ids = {row["sample_person_id"] for row in rows}
    missing, extra = sorted(census_ids - prediction_ids), sorted(prediction_ids - census_ids)
    if missing or extra:
        raise ContractError(f"strict ID coverage failed; missing={missing}, extra={extra}")
    output = []
    conversion_count = 0
    by_id = {row["sample_person_id"]: row for row in rows}
    for person_id in sorted(census_ids):
        source = by_id[person_id]
        try:
            numeric = float(source["prediction_value"])
        except ValueError as exc:
            raise ContractError("prediction values must be numeric") from exc
        value = to_linear_ars(numeric, source_transform)
        conversion_count += int(source_transform != "linear_ars")
        output.append({**source, "prediction_value": value, "prediction_transform": "linear_ars",
                       "source_prediction_transform": source_transform})
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    qa = {
        "release_id": release.manifest["release_id"], "manifest_sha256": release.manifest_hash,
        "input_row_counts": {"predictions": len(rows), "census_persons": len(census_ids)},
        "key_uniqueness": True, "sample_id_namespace": sample_id_namespace, "period": selected_period,
        "source_prediction_transform": source_transform, "output_prediction_transform": "linear_ars",
        "conversion_count": conversion_count, "missing_id_count": 0, "extra_id_count": 0,
        "output_row_counts": {"predictions": len(output)},
        "output_hashes": {"predictions": hashlib.sha256(payload.encode()).hexdigest()},
        "retransformation_limitation": "Mechanical inversion is not an unbiased expected income estimate.",
        "scientific_execution_performed": False,
    }
    return output, qa
