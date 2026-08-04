"""Explicit local GeoJSON adapter for downstream publication systems."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from poverty_pipeline.aggregation import TidyEstimate


def write_department_geojson(features: Iterable[Mapping[str, object]],
                             estimates: Iterable[TidyEstimate], destination: str | Path) -> Path:
    """Join department estimates onto supplied features and write GeoJSON.

    This adapter performs no upload and has no Mapbox or other remote client.
    Features must expose the CPV-2010 identifier as ``department_id``.
    """
    lookup: dict[str, dict[str, float]] = {}
    for row in estimates:
        if row.geography_level == "department_2010":
            lookup.setdefault(row.geography_id, {})[f"{row.universe}_{row.observable}_{row.statistic}"] = row.value
    output = []
    for feature in features:
        copied = json.loads(json.dumps(feature))
        department = str(copied.get("properties", {}).get("department_id", ""))
        if department not in lookup:
            raise ValueError(f"GeoJSON department has no estimate: {department!r}")
        copied["properties"].update(lookup[department])
        output.append(copied)
    result = Path(destination)
    result.write_text(json.dumps({"type": "FeatureCollection", "features": output},
                                 ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    return result
