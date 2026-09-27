#!/usr/bin/env python3
"""Validate and summarize the cross-ecosystem commissioning registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = Path(__file__).with_name("registry.json")
SCHEMA = "poverty-ecosystem-commissioning-registry/v1"
STATUSES = {
    "closed_pass",
    "closed_negative",
    "diagnostic_only",
    "revalidate",
    "blocked",
    "superseded",
}
STAGES = {
    "truth",
    "within_domain_model",
    "transport",
    "calibration",
    "downstream_impact",
    "observability",
}


class RegistryError(ValueError):
    pass


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA:
        raise RegistryError(f"unexpected registry schema: {data.get('schema_version')}")
    return data


def _require_text(record: dict[str, Any], key: str, context: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{context} missing nonempty {key}")


def validate_registry(data: dict[str, Any]) -> dict[str, Any]:
    vocabulary = data.get("status_vocabulary")
    if not isinstance(vocabulary, dict) or set(vocabulary) != STATUSES:
        raise RegistryError(
            f"status vocabulary mismatch: {sorted(vocabulary or {})} != {sorted(STATUSES)}"
        )

    invariants = data.get("invariants") or {}
    if invariants.get("census_design_inverse_probability_is_analysis_weight") is not False:
        raise RegistryError("Census design inverse probability must remain non-analysis weight")
    if invariants.get("no_generic_raking_or_ipf") is not True:
        raise RegistryError("generic raking/IPF must remain disabled")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise RegistryError("registry surfaces must be a nonempty list")

    by_id: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise RegistryError("surface entry must be an object")
        sid = surface.get("id")
        if not isinstance(sid, str) or not sid:
            raise RegistryError("surface missing id")
        if sid in by_id:
            raise RegistryError(f"duplicate surface id: {sid}")
        by_id[sid] = surface

        for key in (
            "name",
            "family",
            "stage",
            "question",
            "outcome_authority",
            "entity_geography",
            "promotion_role",
            "rerun_trigger",
        ):
            _require_text(surface, key, sid)

        if surface["stage"] not in STAGES:
            raise RegistryError(f"{sid} unsupported stage: {surface['stage']}")

        authority = surface.get("authority") or {}
        _require_text(authority, "repository", f"{sid}.authority")
        _require_text(authority, "path", f"{sid}.authority")

        current = surface.get("current") or {}
        status = current.get("status")
        if status not in STATUSES - {"superseded"}:
            raise RegistryError(f"{sid} unsupported active status: {status}")
        _require_text(current, "scope", f"{sid}.current")
        evidence = current.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise RegistryError(f"{sid}.current evidence must be a nonempty string list")

        deps = surface.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
            raise RegistryError(f"{sid} depends_on must be a string list")

        if not isinstance(surface.get("weights"), dict):
            raise RegistryError(f"{sid} weights must be explicit")
        if not isinstance(surface.get("calibration"), dict):
            raise RegistryError(f"{sid} calibration must be explicit")

    missing = sorted(
        {dep for surface in surfaces for dep in surface["depends_on"] if dep not in by_id}
    )
    if missing:
        raise RegistryError(f"unknown dependencies: {missing}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(sid: str) -> None:
        if sid in visited:
            return
        if sid in visiting:
            raise RegistryError(f"dependency cycle detected at {sid}")
        visiting.add(sid)
        for dep in by_id[sid]["depends_on"]:
            visit(dep)
        visiting.remove(sid)
        visited.add(sid)

    for sid in by_id:
        visit(sid)

    superseded = data.get("superseded")
    if not isinstance(superseded, list):
        raise RegistryError("superseded must be a list")
    historical_ids: set[str] = set()
    for item in superseded:
        if not isinstance(item, dict):
            raise RegistryError("superseded entry must be an object")
        _require_text(item, "id", "superseded")
        if item["id"] in historical_ids or item["id"] in by_id:
            raise RegistryError(f"duplicate historical id: {item['id']}")
        historical_ids.add(item["id"])
        if item.get("status") != "superseded":
            raise RegistryError(f"{item['id']} must have superseded status")
        _require_text(item, "replaced_by", item["id"])
        _require_text(item, "keep_for", item["id"])
        _require_text(item, "reason", item["id"])

    return {
        "schema_version": SCHEMA,
        "active_surfaces": len(by_id),
        "historical_surfaces": len(historical_ids),
        "statuses": {
            status: sum(1 for surface in surfaces if surface["current"]["status"] == status)
            for status in sorted(STATUSES - {"superseded"})
        },
    }


def render_summary(data: dict[str, Any]) -> str:
    lines = [
        "# Commissioning registry",
        "",
        f"As of: {data['as_of']}",
        "",
        "| ID | Stage | Current status | Scope |",
        "|---|---|---|---|",
    ]
    for surface in data["surfaces"]:
        current = surface["current"]
        lines.append(
            f"| {surface['id']} | {surface['stage']} | {current['status']} | {current['scope']} |"
        )
    if data.get("superseded"):
        lines.extend(["", "## Superseded / historical"])
        for item in data["superseded"]:
            lines.append(
                f"- **{item['id']}** → {item['replaced_by']}: {item['keep_for']}."
            )
    return "\n".join(lines) + "\n"


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    out.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    out.add_argument("--summary", action="store_true")
    return out


def main() -> int:
    args = parser().parse_args()
    data = load_registry(args.registry)
    result = validate_registry(data)
    if args.summary:
        print(render_summary(data), end="")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
