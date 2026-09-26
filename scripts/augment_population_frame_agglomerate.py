#!/usr/bin/env python3
"""Attach nullable EPH agglomerate identity to an existing population-frame JSON.

The geography patch is produced by samplerCensoARG's governed A7 sidecar. This
script changes no household/person membership, welfare, weights, or poverty
semantics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class PopulationFrameAgglomerateError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PopulationFrameAgglomerateError(f"invalid_json:{path}") from exc


def augment_population_frame(frame: dict, patch: dict) -> tuple[dict, dict]:
    households = frame.get("households")
    persons = frame.get("persons")
    if not isinstance(households, list) or not isinstance(persons, list):
        raise PopulationFrameAgglomerateError(
            "population frame must contain households and persons arrays"
        )
    if patch.get("schema_version") != "research.population-frame-geography-patch/v1":
        raise PopulationFrameAgglomerateError("unsupported geography patch schema")
    if patch.get("household_key") != "household_id":
        raise PopulationFrameAgglomerateError("geography patch must use household_id")
    if patch.get("geography_field") != "eph_agglomerate_id":
        raise PopulationFrameAgglomerateError("unexpected geography patch field")
    patch_rows = patch.get("rows")
    if not isinstance(patch_rows, list):
        raise PopulationFrameAgglomerateError("geography patch rows must be an array")

    household_ids = [str(row.get("household_id", "")) for row in households]
    if not all(household_ids) or len(set(household_ids)) != len(household_ids):
        raise PopulationFrameAgglomerateError(
            "population frame household IDs must be nonempty and unique"
        )
    patch_ids = [str(row.get("household_id", "")) for row in patch_rows]
    if not all(patch_ids) or len(set(patch_ids)) != len(patch_ids):
        raise PopulationFrameAgglomerateError(
            "geography patch household IDs must be nonempty and unique"
        )
    if set(household_ids) != set(patch_ids):
        missing = sorted(set(household_ids) - set(patch_ids))
        extra = sorted(set(patch_ids) - set(household_ids))
        raise PopulationFrameAgglomerateError(
            f"frame/patch household identity mismatch: missing={missing[:20]} extra={extra[:20]}"
        )

    by_id = {str(row["household_id"]): row for row in patch_rows}
    out_households = []
    mapped = 0
    represented: set[str] = set()
    for source in households:
        row = dict(source)
        household_id = str(row["household_id"])
        patch_row = by_id[household_id]
        value = patch_row.get("eph_agglomerate_id")
        mapped_flag = bool(patch_row.get("mapped_to_eph_frame"))
        if value is None:
            if mapped_flag:
                raise PopulationFrameAgglomerateError(
                    f"mapped household lacks eph_agglomerate_id: {household_id}"
                )
            normalized = None
        else:
            normalized = str(value)
            if len(normalized) != 2 or not normalized.isdigit():
                raise PopulationFrameAgglomerateError(
                    f"invalid eph_agglomerate_id for {household_id}: {normalized!r}"
                )
            if not mapped_flag:
                raise PopulationFrameAgglomerateError(
                    f"unmapped household claims eph_agglomerate_id: {household_id}"
                )
            mapped += 1
            represented.add(normalized)

        existing = row.get("eph_agglomerate_id")
        if existing not in (None, "") and str(existing) != str(normalized):
            raise PopulationFrameAgglomerateError(
                f"existing agglomerate identity conflicts for {household_id}"
            )
        row["eph_agglomerate_id"] = normalized
        row["mapped_to_eph_frame"] = mapped_flag
        out_households.append(row)

    out = dict(frame)
    out["households"] = out_households
    out["geography_handoff"] = {
        "schema_version": "research.population-frame-geography-handoff/v1",
        "field": "eph_agglomerate_id",
        "nullable": True,
        "membership": "direct official A7 radio relation via samplerCensoARG sidecar",
        "outside_eph_frame_policy": "preserve household with null eph_agglomerate_id",
        "sampling_changed": False,
        "weights_changed": False,
        "model_changed": False,
    }
    qa = {
        "household_count": len(out_households),
        "person_count": len(persons),
        "mapped_to_eph_frame_households": mapped,
        "outside_eph_frame_households": len(out_households) - mapped,
        "represented_eph_agglomerate_ids": sorted(represented),
        "represented_eph_agglomerate_count": len(represented),
        "household_order_preserved": [
            str(row["household_id"]) for row in out_households
        ] == household_ids,
        "person_payload_unchanged": out["persons"] == persons,
        "sampling_changed": False,
        "weights_changed": False,
        "model_changed": False,
    }
    return out, qa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--geography-patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frame = _load(args.frame)
    patch = _load(args.geography_patch)
    if not isinstance(frame, dict) or not isinstance(patch, dict):
        raise PopulationFrameAgglomerateError("inputs must be JSON objects")
    out, qa = augment_population_frame(frame, patch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    qa_path = args.output.with_suffix(args.output.suffix + ".qa.json")
    qa_path.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
