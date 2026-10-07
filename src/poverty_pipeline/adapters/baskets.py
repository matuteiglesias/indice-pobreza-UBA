"""Strict adapter for governed canastasINDEC Poverty quarter-slice artifacts.

This boundary validates producer-owned basket evidence and maps it into Poverty's
existing PovertyLineRelease contract. It performs no network access, geography
inference, adult-equivalence work, or poverty classification.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any

from poverty_pipeline.contracts import ContractError
from poverty_pipeline.contracts_v2 import PovertyLine, PovertyLineRelease

ARTIFACT_TYPE = "research.argentina-regional-baskets-poverty-input/v1"
METHOD_ID = "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"
MONETARY_REFERENCE_ID = (
    "research.argentina-price-consensus/curated-official-panel-v2@2016-01=100"
)
REGIONS = (
    "gran_buenos_aires",
    "cuyo",
    "noreste",
    "noroeste",
    "pampeana",
    "patagonia",
)
ALLOWED_STATUSES = {"candidate", "reviewed", "approved"}
EXPECTED_COLUMNS = (
    "period",
    "representative_date",
    "region_id",
    "CBA_2016_01",
    "CBT_2016_01",
    "unit",
    "monetary_reference_id",
    "status",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(reason) from exc
    if not isinstance(value, dict):
        raise ContractError(reason)
    return value


def _safe_file(root: Path, name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or "\\" in name:
        raise ContractError(f"unsafe basket payload path: {name!r}")
    target = (root / name).resolve()
    root = root.resolve()
    if target == root or root not in target.parents or not target.is_file():
        raise ContractError(f"missing or unsafe basket payload: {name!r}")
    return target


def _validate_payloads(root: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ContractError("basket manifest files must be a nonempty object")
    for name, identity in files.items():
        if not isinstance(name, str) or not isinstance(identity, dict):
            raise ContractError("invalid basket file identity")
        path = _safe_file(root, name)
        try:
            declared_size = int(identity["bytes"])
            declared_sha = str(identity["sha256"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("invalid basket file identity") from exc
        if path.stat().st_size != declared_size or _sha256(path) != declared_sha:
            raise ContractError(f"basket payload identity mismatch: {name}")


def _positive_number(value: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise ContractError(f"{label} must be finite and positive")
    return number


def adapt_canastas_poverty_slice(
    release_root: str | Path,
    *,
    poverty_method_release_id: str,
    expected_period: str | None = None,
    allowed_statuses: set[str] = ALLOWED_STATUSES,
) -> tuple[PovertyLineRelease, dict[str, Any]]:
    """Validate one immutable quarter slice and map it to PovertyLineRelease."""
    root = Path(release_root).resolve()
    manifest_path = root / "manifest.json"
    manifest = _load_json(manifest_path, "missing_or_invalid_basket_manifest")

    if manifest.get("schema") != "research-artifact-manifest/v1":
        raise ContractError("unsupported basket manifest schema")
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise ContractError("unexpected basket artifact type")
    if manifest.get("method_id") != METHOD_ID:
        raise ContractError("unexpected basket method identity")
    if manifest.get("status") not in allowed_statuses:
        raise ContractError("basket release status is not allowed")
    if manifest.get("release_id") != root.name:
        raise ContractError("basket release directory/identity mismatch")
    period = manifest.get("period")
    if not isinstance(period, str) or not period:
        raise ContractError("basket period is required")
    if expected_period is not None and period != expected_period:
        raise ContractError("basket period does not match requested period")
    if manifest.get("monetary_reference_id") != MONETARY_REFERENCE_ID:
        raise ContractError("unexpected basket monetary reference")
    if manifest.get("unit") != "ARS_per_equivalent_adult":
        raise ContractError("unexpected basket unit")
    if manifest.get("scientific_poverty_execution_performed") is not False:
        raise ContractError("upstream basket artifact must not claim poverty execution")
    if tuple(manifest.get("regions") or ()) != REGIONS:
        raise ContractError("basket region identity/order mismatch")

    _validate_payloads(root, manifest)
    table = root / "regional_baskets.csv"
    if not table.is_file():
        raise ContractError("basket slice is missing regional_baskets.csv")
    with table.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ContractError("basket table schema or column order mismatch")
        rows = list(reader)

    if len(rows) != len(REGIONS):
        raise ContractError("basket slice must contain exactly six regional rows")
    by_region: dict[str, PovertyLine] = {}
    for row in rows:
        region = row["region_id"]
        if region in by_region:
            raise ContractError(f"duplicate basket region: {region}")
        if region not in REGIONS:
            raise ContractError(f"unknown basket region: {region}")
        if row["period"] != period:
            raise ContractError("basket row period mismatch")
        if row["monetary_reference_id"] != MONETARY_REFERENCE_ID:
            raise ContractError("basket row monetary reference mismatch")
        if row["unit"] != "ARS_per_equivalent_adult":
            raise ContractError("basket row unit mismatch")
        if row["status"] != "candidate":
            raise ContractError("current basket slice row status must remain candidate")
        cba = _positive_number(row["CBA_2016_01"], "CBA")
        cbt = _positive_number(row["CBT_2016_01"], "CBT")
        if cba > cbt:
            raise ContractError("CBA must not exceed CBT")
        by_region[region] = PovertyLine(region, cba, cbt)

    if set(by_region) != set(REGIONS):
        raise ContractError("basket slice does not exactly cover six threshold areas")
    if not isinstance(poverty_method_release_id, str) or not poverty_method_release_id.strip():
        raise ContractError("poverty method release id is required")

    lines = PovertyLineRelease(
        release_id=manifest["release_id"],
        period=period,
        currency="ARS",
        price_reference=MONETARY_REFERENCE_ID,
        method_release_id=poverty_method_release_id,
        lines=tuple(by_region[region] for region in REGIONS),
    )
    price_dependency = manifest.get("price_dependency")
    qa = {
        "source_artifact_type": ARTIFACT_TYPE,
        "source_release_id": manifest["release_id"],
        "source_manifest_sha256": _sha256(manifest_path),
        "source_status": manifest["status"],
        "period": period,
        "threshold_area_count": len(lines.lines),
        "threshold_area_ids": list(REGIONS),
        "currency": "ARS",
        "price_reference": MONETARY_REFERENCE_ID,
        "poverty_method_release_id": poverty_method_release_id,
        "price_dependency": price_dependency,
        "scientific_execution_performed": False,
    }
    return lines, qa
