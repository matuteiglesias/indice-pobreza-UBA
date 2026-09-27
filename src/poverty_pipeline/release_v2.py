"""Deterministic packaging for Poverty Estimation v2 aggregate releases.

The release contains tidy estimates plus explicit consumer capabilities and a
geography foreign-key contract, never geometry. Mapping/web consumers join
against separately governed geography products and must not infer capabilities
from producer implementation details.
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
_ALLOWED_STATUS = {"synthetic_fixture", "research_estimate"}
_NON_SPATIAL_LEVELS = {"national", "eph_coverage"}
_CAPABILITY_SCHEMA = "poverty-estimate-capabilities/v2"
_PERMISSION_VALUES = {
    "point_estimates": {"authorized", "demo_only"},
    "population_counts": {"not_authorized"},
    "uncertainty_intervals": {"not_authorized"},
    "inferential_ranking": {"not_authorized"},
    "temporal_comparison": {"descriptive_only", "demo_only"},
}
_INTERPRETATION_MODES = {"demo_only", "commissioning_only", "research_public"}


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


def _availability(rows: list[object]) -> list[dict[str, object]]:
    """Return exact selectable measure/geography cells exposed by the release."""
    groups: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (
            row.estimation_period,
            row.universe,
            row.geography_level,
            row.concept,
            row.estimand,
        )
        cell = groups.setdefault(key, {
            "estimation_period": row.estimation_period,
            "universe": row.universe,
            "geography_level": row.geography_level,
            "concept": row.concept,
            "estimand": row.estimand,
            "unit": row.unit,
            "uncertainty_status": row.uncertainty_status,
            "geography_count": 0,
        })
        if cell["unit"] != row.unit or cell["uncertainty_status"] != row.uncertainty_status:
            raise EstimateReleaseError("one availability cell must have stable unit/uncertainty semantics")
        cell["geography_count"] = int(cell["geography_count"]) + 1
    return [groups[key] for key in sorted(groups)]


def _capability_permissions(
    *,
    status: str,
    not_for_interpretation: bool,
) -> dict[str, object]:
    if status == "synthetic_fixture":
        interpretation = "demo_only"
        point_estimates = "demo_only"
        temporal_comparison = "demo_only"
    else:
        interpretation = (
            "commissioning_only" if not_for_interpretation else "research_public"
        )
        point_estimates = "authorized"
        temporal_comparison = "descriptive_only"
    return {
        "interpretation": interpretation,
        "operations": {
            "point_estimates": point_estimates,
            "population_counts": "not_authorized",
            "uncertainty_intervals": "not_authorized",
            "inferential_ranking": "not_authorized",
            "temporal_comparison": temporal_comparison,
        },
    }


def _recommended_map_measure(availability: list[dict[str, object]]) -> dict[str, str] | None:
    candidates = [cell for cell in availability if cell["geography_level"] != "national"]
    preferred = [cell for cell in candidates
                 if cell["universe"] == "persons"
                 and cell["concept"] == "poverty"
                 and cell["estimand"] == "fgt0"]
    selected = (preferred or candidates)
    if not selected:
        return None
    cell = selected[0]
    return {key: str(cell[key]) for key in (
        "estimation_period", "universe", "geography_level", "concept", "estimand"
    )}


def write_estimate_release(
    root: str | Path,
    estimation: PovertyEstimation,
    *,
    parents: tuple[ParentReleaseRef, ...],
    method_release_id: str,
    status: str = "synthetic_fixture",
    not_for_interpretation: bool = True,
) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise EstimateReleaseError("release directory must be empty")
    if not estimation.estimates:
        raise EstimateReleaseError("poverty estimation must contain rows")
    if status not in _ALLOWED_STATUS:
        raise EstimateReleaseError(f"unsupported scientific status: {status!r}")
    if not isinstance(not_for_interpretation, bool):
        raise EstimateReleaseError("not_for_interpretation must be boolean")
    if status == "synthetic_fixture" and not_for_interpretation is not True:
        raise EstimateReleaseError("synthetic fixtures must remain not_for_interpretation")
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
    method_parents = [parent for parent in parents if parent.role == "poverty_method"]
    if len(method_parents) != 1 or method_parents[0].release_id != method_release_id:
        raise EstimateReleaseError("poverty_method parent must exactly match method_release_id")

    rows = sorted(
        estimation.estimates,
        key=lambda row: (
            row.universe, row.geography_level, row.geography_id,
            row.concept, row.estimand,
        ),
    )
    release_ids = {row.release_id for row in rows}
    periods = {row.estimation_period for row in rows}
    frame_vintages = {row.frame_vintage for row in rows}
    if len(release_ids) != 1 or len(periods) != 1 or len(frame_vintages) != 1:
        raise EstimateReleaseError("all estimate rows must share release, period and frame vintage")

    estimates_path = root / "poverty_estimates.csv"
    with estimates_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ESTIMATE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in ESTIMATE_FIELDS})

    availability = _availability(rows)
    joinable_levels = sorted({
        row.geography_level for row in rows
        if row.geography_level not in _NON_SPATIAL_LEVELS
    })
    non_spatial_levels = sorted({
        row.geography_level for row in rows
        if row.geography_level in _NON_SPATIAL_LEVELS
    })
    weight_semantics = sorted({row.weight_semantics for row in rows})
    design_ids = sorted({row.design_id for row in rows})
    units = sorted({row.unit for row in rows})
    if units != ["proportion"]:
        raise EstimateReleaseError("capability contract currently authorizes proportions only")
    if len(weight_semantics) != 1:
        raise EstimateReleaseError("release must have one analysis-weight semantics")
    capabilities = {
        "schema_version": _CAPABILITY_SCHEMA,
        "release_id": rows[0].release_id,
        "scientific_status": status,
        "not_for_interpretation": not_for_interpretation,
        "geometry_embedded": False,
        "estimand_contract": {
            "measure": "proportion",
            "universes": sorted({row.universe for row in rows}),
            "analysis_weight_semantics": weight_semantics[0],
            "design_ids": design_ids,
            "population_mass_authority": None,
            "household_total_authority": False,
        },
        "permissions": _capability_permissions(
            status=status,
            not_for_interpretation=not_for_interpretation,
        ),
        "dimensions": {
            "estimation_periods": sorted(periods),
            "universes": sorted({row.universe for row in rows}),
            "geography_levels": sorted({row.geography_level for row in rows}),
            "concepts": sorted({row.concept for row in rows}),
            "estimands": sorted({row.estimand for row in rows}),
        },
        "availability": availability,
    }
    _write_json(root / "capabilities.json", capabilities)

    join_contract = {
        "schema_version": "poverty-geography-join/v1",
        "geometry_embedded": False,
        "geometry_owner": "matuteiglesias/argentina-geography",
        "fact_table": "poverty_estimates.csv",
        "capabilities": "capabilities.json",
        "fact_key": [
            "release_id", "estimation_period", "universe", "geography_level",
            "geography_id", "concept", "estimand",
        ],
        "join_key": ["geography_level", "geography_id"],
        "join_semantics": "exact_governed_id",
        "joinable_geography_levels": joinable_levels,
        "non_spatial_levels": non_spatial_levels,
        "recommended_map_measure": _recommended_map_measure(availability),
    }
    _write_json(root / "geography_join_contract.json", join_contract)

    first = rows[0]
    manifest = {
        "schema_version": "poverty-estimate-release/v2",
        "release_id": first.release_id,
        "estimation_period": first.estimation_period,
        "frame_vintage": first.frame_vintage,
        "scientific_status": status,
        "not_for_interpretation": not_for_interpretation,
        "method_release_id": method_release_id,
        "parents": [asdict(parent) for parent in parents],
        "output_roles": {
            "estimates": "poverty_estimates.csv",
            "capabilities": "capabilities.json",
            "geography_join_contract": "geography_join_contract.json",
            "qa": "run_qa.json",
            "limitations": "LIMITATIONS.md",
            "checksums": "checksums.sha256",
        },
        "uncertainty_status": estimation.qa.uncertainty_status,
        "geometry_embedded": False,
    }
    aggregate_rows = [
        row for row in rows if row.geography_level in _NON_SPATIAL_LEVELS
    ]
    aggregate_identities = sorted({
        (row.geography_level, row.geography_id) for row in aggregate_rows
    })
    if len(aggregate_identities) != 1:
        raise EstimateReleaseError(
            "release must expose exactly one aggregate geography identity"
        )
    aggregate_level, aggregate_id = aggregate_identities[0]
    if (aggregate_level, aggregate_id) != ("national", "ARG"):
        manifest["aggregate_geography"] = {
            "level": aggregate_level,
            "id": aggregate_id,
        }
    _write_json(root / "release_manifest.json", manifest)

    qa = asdict(estimation.qa) | {
        "schema_version": "poverty-estimate-qa/v2",
        "estimate_rows": len(rows),
        "estimate_min": min(row.estimate for row in rows),
        "estimate_max": max(row.estimate for row in rows),
        "joinable_geography_levels": joinable_levels,
        "joinable_rows_by_level": {
            level: sum(row.geography_level == level for row in rows) for level in joinable_levels
        },
        "geometry_embedded": False,
    }
    _write_json(root / "run_qa.json", qa)

    limitations = [
        "# Limitations",
        "",
        "- This is a research-system output and must not be presented as an official INDEC poverty statistic.",
        "- Geography is represented only by governed IDs. Geometry must be joined externally.",
    ]
    if status == "synthetic_fixture":
        limitations.insert(2, "- Values are synthetic fixture data and are not interpretable poverty estimates.")
    elif not_for_interpretation:
        limitations.insert(
            2,
            "- This release is restricted to commissioning/inspection and is not authorized for ordinary public interpretation.",
        )
    if estimation.qa.uncertainty_status == "not_supplied":
        limitations.append("- No uncertainty input was supplied; standard errors and confidence intervals are unavailable.")
    (root / "LIMITATIONS.md").write_text("\n".join(limitations) + "\n", encoding="utf-8")

    checksum_targets = [
        "poverty_estimates.csv", "capabilities.json", "geography_join_contract.json",
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
        "poverty_estimates.csv", "capabilities.json", "geography_join_contract.json",
        "release_manifest.json", "run_qa.json", "LIMITATIONS.md", "checksums.sha256",
    }
    if {path.name for path in root.iterdir()} != required:
        raise EstimateReleaseError("estimate release file set does not match v2 contract")

    checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    if len(checksum_lines) != 6:
        raise EstimateReleaseError("unexpected checksum entry count")
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        if not _SHA256.fullmatch(digest) or digest != _sha(root / name):
            raise EstimateReleaseError(f"checksum mismatch: {name}")

    manifest = json.loads((root / "release_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "poverty-estimate-release/v2":
        raise EstimateReleaseError("unsupported estimate release schema")
    if manifest.get("scientific_status") not in _ALLOWED_STATUS:
        raise EstimateReleaseError("invalid scientific status")
    if manifest.get("geometry_embedded") is not False:
        raise EstimateReleaseError("poverty estimate release must not embed geometry")
    parents = manifest.get("parents")
    if not isinstance(parents, list) or not parents:
        raise EstimateReleaseError("manifest must retain parent release refs")
    for parent in parents:
        if not _SHA256.fullmatch(parent.get("content_sha256", "")):
            raise EstimateReleaseError("manifest parent hash is invalid")
    method_parent = [parent for parent in parents if parent.get("role") == "poverty_method"]
    if len(method_parent) != 1 or method_parent[0].get("release_id") != manifest.get("method_release_id"):
        raise EstimateReleaseError("manifest poverty method identity is inconsistent")

    join = json.loads((root / "geography_join_contract.json").read_text(encoding="utf-8"))
    if join.get("geometry_embedded") is not False or join.get("join_key") != ["geography_level", "geography_id"]:
        raise EstimateReleaseError("invalid geography join contract")
    if join.get("join_semantics") != "exact_governed_id":
        raise EstimateReleaseError("unsupported geography join semantics")

    capabilities = json.loads((root / "capabilities.json").read_text(encoding="utf-8"))
    if capabilities.get("schema_version") != _CAPABILITY_SCHEMA:
        raise EstimateReleaseError("unsupported capabilities schema")
    if capabilities.get("release_id") != manifest.get("release_id"):
        raise EstimateReleaseError("capabilities release identity mismatch")
    if capabilities.get("scientific_status") != manifest.get("scientific_status"):
        raise EstimateReleaseError("capabilities scientific status mismatch")
    if capabilities.get("not_for_interpretation") != manifest.get("not_for_interpretation"):
        raise EstimateReleaseError("capabilities interpretation status mismatch")
    if capabilities.get("geometry_embedded") is not False:
        raise EstimateReleaseError("capabilities must remain geometry-free")

    estimand_contract = capabilities.get("estimand_contract")
    if not isinstance(estimand_contract, dict):
        raise EstimateReleaseError("capabilities require estimand_contract")
    if estimand_contract.get("measure") != "proportion":
        raise EstimateReleaseError("only proportion estimands are authorized")
    if estimand_contract.get("population_mass_authority") is not None:
        raise EstimateReleaseError("current release contract has no population-mass authority")
    if estimand_contract.get("household_total_authority") is not False:
        raise EstimateReleaseError("current release contract has no household-total authority")

    permissions = capabilities.get("permissions")
    if not isinstance(permissions, dict):
        raise EstimateReleaseError("capabilities require permissions")
    interpretation = permissions.get("interpretation")
    if interpretation not in _INTERPRETATION_MODES:
        raise EstimateReleaseError("unsupported interpretation permission")
    operations = permissions.get("operations")
    if not isinstance(operations, dict):
        raise EstimateReleaseError("capabilities permissions require operations")
    if set(operations) != set(_PERMISSION_VALUES):
        raise EstimateReleaseError("capability operation set mismatch")
    for name, allowed in _PERMISSION_VALUES.items():
        if operations.get(name) not in allowed:
            raise EstimateReleaseError(f"unsupported {name} permission")
    if operations.get("population_counts") != "not_authorized":
        raise EstimateReleaseError("counts require a future population-mass authority")
    if manifest.get("uncertainty_status") == "not_supplied" and (
        operations.get("uncertainty_intervals") != "not_authorized"
        or operations.get("inferential_ranking") != "not_authorized"
    ):
        raise EstimateReleaseError(
            "uncertainty/ranking cannot be authorized when uncertainty is not supplied"
        )
    if manifest.get("scientific_status") == "synthetic_fixture":
        if manifest.get("not_for_interpretation") is not True:
            raise EstimateReleaseError("synthetic fixture must be not_for_interpretation")
        if interpretation != "demo_only":
            raise EstimateReleaseError("synthetic fixture must use demo_only interpretation")
    elif manifest.get("not_for_interpretation") is True:
        if interpretation != "commissioning_only":
            raise EstimateReleaseError(
                "not_for_interpretation research release must be commissioning_only"
            )
    elif interpretation != "research_public":
        raise EstimateReleaseError(
            "interpretable research release must use research_public interpretation"
        )

    with (root / "poverty_estimates.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ESTIMATE_FIELDS:
            raise EstimateReleaseError("poverty estimate schema mismatch")
        seen: set[tuple[str, ...]] = set()
        rows = []
        for row in reader:
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
            if row["release_id"] != manifest.get("release_id"):
                raise EstimateReleaseError("estimate row release identity mismatch")
            if row["estimation_period"] != manifest.get("estimation_period"):
                raise EstimateReleaseError("estimate row period mismatch")
            if row["frame_vintage"] != manifest.get("frame_vintage"):
                raise EstimateReleaseError("estimate row frame vintage mismatch")
            rows.append(row)
        if not rows:
            raise EstimateReleaseError("poverty estimate table must be nonempty")

    joinable_levels = sorted({
        row["geography_level"] for row in rows
        if row["geography_level"] not in _NON_SPATIAL_LEVELS
    })
    if join.get("joinable_geography_levels") != joinable_levels:
        raise EstimateReleaseError("geography join levels do not match estimate facts")
    non_spatial_levels = sorted({
        row["geography_level"] for row in rows
        if row["geography_level"] in _NON_SPATIAL_LEVELS
    })
    if join.get("non_spatial_levels") != non_spatial_levels:
        raise EstimateReleaseError("non-spatial geography levels do not match estimate facts")
    aggregate_ids = {
        (row["geography_level"], row["geography_id"])
        for row in rows
        if row["geography_level"] in _NON_SPATIAL_LEVELS
    }
    if len(aggregate_ids) != 1:
        raise EstimateReleaseError("estimate facts require one aggregate geography identity")
    aggregate_level, aggregate_id = next(iter(aggregate_ids))
    declared_aggregate = manifest.get("aggregate_geography")
    if (aggregate_level, aggregate_id) == ("national", "ARG"):
        if declared_aggregate is not None:
            raise EstimateReleaseError("legacy national/ARG release must not add aggregate metadata")
    elif declared_aggregate != {"level": aggregate_level, "id": aggregate_id}:
        raise EstimateReleaseError("aggregate geography metadata does not match facts")
    observed_weight_semantics = sorted({row["weight_semantics"] for row in rows})
    observed_design_ids = sorted({row["design_id"] for row in rows})
    observed_universes = sorted({row["universe"] for row in rows})
    if estimand_contract.get("analysis_weight_semantics") != observed_weight_semantics[0]:
        raise EstimateReleaseError("estimand analysis-weight semantics differ from facts")
    if estimand_contract.get("design_ids") != observed_design_ids:
        raise EstimateReleaseError("estimand design IDs differ from facts")
    if estimand_contract.get("universes") != observed_universes:
        raise EstimateReleaseError("estimand universes differ from facts")

    availability = capabilities.get("availability")
    if not isinstance(availability, list) or not availability:
        raise EstimateReleaseError("capabilities must expose nonempty availability")
    declared_cells = {
        (cell.get("estimation_period"), cell.get("universe"), cell.get("geography_level"),
         cell.get("concept"), cell.get("estimand")): cell.get("geography_count")
        for cell in availability
    }
    observed_cells: dict[tuple[str, str, str, str, str], int] = {}
    for row in rows:
        key = (row["estimation_period"], row["universe"], row["geography_level"],
               row["concept"], row["estimand"])
        observed_cells[key] = observed_cells.get(key, 0) + 1
    if declared_cells != observed_cells:
        raise EstimateReleaseError("capabilities availability does not match estimate facts")
