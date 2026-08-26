"""Deterministic packaging for Poverty Estimation v2 aggregate releases.

The release contains tidy estimates and a geography foreign-key contract, never
geometry. Mapping/web consumers join against a separately governed geography
product.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from poverty_pipeline.estimation_v2 import PovertyEstimation


class EstimateReleaseError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ParentReleaseRef:
    role: str
    release_id: str
    content_sha256: str


ESTIMATE_FIELDS = (
    "release_id", "estimation_period", "frame_vintage", "universe",
    "geography_level", "geography_id", "concept", "estimand", "estimate",
    "unit", "weighted_numerator", "weighted_denominator", "coverage",
    "design_id", "weight_semantics", "uncertainty_status",
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_estimate_release(
    root: str | Path,
    estimation: PovertyEstimation,
    *,
    parents: tuple[ParentReleaseRef, ...],
    method_release_id: str,
    status: str = "synthetic_fixture",
) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise EstimateReleaseError("release directory must be empty")
    if not estimation.estimates:
        raise EstimateReleaseError("poverty estimation must contain rows")
    if not parents:
        raise EstimateReleaseError("estimate release requires exact parent refs")
    roles: set[str] = set()
    for parent in parents:
        if not parent.role or not parent.release_id or parent.role in roles:
            raise EstimateReleaseError("parent roles/release IDs must be nonempty and unique")
        if not _SHA256.fullmatch(parent.content_sha256):
            raise EstimateReleaseError("parent content_sha256 must be a lowercase SHA-256")
        roles.add(parent.role)
    if not method_release_id:
        raise EstimateReleaseError("method_release_id must be nonempty")

    rows = sorted(
        estimation.estimates,
        key=lambda row: (
            row.universe, row.geography_level, row.geography_id,
            row.concept, row.estimand,
        ),
    )
    estimates_path = root / "poverty_estimates.csv"
    with estimates_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ESTIMATE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in ESTIMATE_FIELDS})

    join_contract = {
        "schema_version": "poverty-geography-join/v1",
        "geometry_embedded": False,
        "geometry_owner": "matuteiglesias/argentina-geography",
        "fact_table": "poverty_estimates.csv",
        "fact_key": [
            "release_id", "estimation_period", "universe", "geography_level",
            "geography_id", "concept", "estimand",
        ],
        "join_key": ["geography_level", "geography_id"],
        "join_semantics": "exact_governed_id",
        "joinable_geography_levels": ["department_2010"],
        "non_spatial_levels": ["national"],
        "recommended_map_measure": {
            "universe": "persons",
            "concept": "poverty",
            "estimand": "fgt0",
        },
    }
    _write_json(root / "geography_join_contract.json", join_contract)

    first = rows[0]
    manifest = {
        "schema_version": "poverty-estimate-release/v2",
        "release_id": first.release_id,
        "estimation_period": first.estimation_period,
        "frame_vintage": first.frame_vintage,
        "status": status,
        "method_release_id": method_release_id,
        "parents": [asdict(parent) for parent in parents],
        "output_roles": {
            "estimates": "poverty_estimates.csv",
            "geography_join_contract": "geography_join_contract.json",
            "qa": "run_qa.json",
            "limitations": "LIMITATIONS.md",
            "checksums": "checksums.sha256",
        },
        "uncertainty_status": estimation.qa.uncertainty_status,
        "geometry_embedded": False,
    }
    _write_json(root / "release_manifest.json", manifest)

    qa = asdict(estimation.qa) | {
        "schema_version": "poverty-estimate-qa/v2",
        "estimate_rows": len(rows),
        "estimate_min": min(row.estimate for row in rows),
        "estimate_max": max(row.estimate for row in rows),
        "joinable_department_rows": sum(row.geography_level == "department_2010" for row in rows),
        "geometry_embedded": False,
    }
    _write_json(root / "run_qa.json", qa)
    (root / "LIMITATIONS.md").write_text(
        "# Limitations\n\n"
        "- This fixture is a research/synthetic estimate, not an official INDEC poverty statistic.\n"
        "- No uncertainty input was supplied; standard errors and confidence intervals are unavailable.\n"
        "- Geography is represented only by governed IDs. Geometry must be joined externally.\n",
        encoding="utf-8",
    )

    checksum_targets = [
        "poverty_estimates.csv", "geography_join_contract.json",
        "release_manifest.json", "run_qa.json", "LIMITATIONS.md",
    ]
    (root / "checksums.sha256").write_text(
        "".join(f"{_sha(root / name)}  {name}\n" for name in checksum_targets),
        encoding="utf-8",
    )
    verify_estimate_release(root)
    return root


def verify_estimate_release(root: str | Path) -> None:
    root = Path(root)
    required = {
        "poverty_estimates.csv", "geography_join_contract.json", "release_manifest.json",
        "run_qa.json", "LIMITATIONS.md", "checksums.sha256",
    }
    if {path.name for path in root.iterdir()} != required:
        raise EstimateReleaseError("estimate release file set does not match v2 contract")

    checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    if len(checksum_lines) != 5:
        raise EstimateReleaseError("unexpected checksum entry count")
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        if not _SHA256.fullmatch(digest) or digest != _sha(root / name):
            raise EstimateReleaseError(f"checksum mismatch: {name}")

    manifest = json.loads((root / "release_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "poverty-estimate-release/v2":
        raise EstimateReleaseError("unsupported estimate release schema")
    if manifest.get("geometry_embedded") is not False:
        raise EstimateReleaseError("poverty estimate release must not embed geometry")
    parents = manifest.get("parents")
    if not isinstance(parents, list) or not parents:
        raise EstimateReleaseError("manifest must retain parent release refs")
    for parent in parents:
        if not _SHA256.fullmatch(parent.get("content_sha256", "")):
            raise EstimateReleaseError("manifest parent hash is invalid")

    join = json.loads((root / "geography_join_contract.json").read_text(encoding="utf-8"))
    if join.get("geometry_embedded") is not False or join.get("join_key") != ["geography_level", "geography_id"]:
        raise EstimateReleaseError("invalid geography join contract")

    with (root / "poverty_estimates.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ESTIMATE_FIELDS:
            raise EstimateReleaseError("poverty estimate schema mismatch")
        seen: set[tuple[str, ...]] = set()
        count = 0
        for row in reader:
            count += 1
            key = tuple(row[field] for field in (
                "release_id", "estimation_period", "universe", "geography_level",
                "geography_id", "concept", "estimand",
            ))
            if key in seen:
                raise EstimateReleaseError(f"duplicate estimate key: {key!r}")
            seen.add(key)
            value = float(row["estimate"])
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise EstimateReleaseError("estimate must be a finite proportion")
            if row["uncertainty_status"] != "not_supplied":
                raise EstimateReleaseError("point-only fixture must not invent uncertainty")
        if count == 0:
            raise EstimateReleaseError("poverty estimate table must be nonempty")
