"""Read-only access to tables emitted by a governed poverty release."""

from __future__ import annotations

import json
import os
import csv
import importlib.util
from pathlib import Path

TABLE_ROLES = (
    "household_classification",
    "person_classification",
    "aggregates_tidy",
    "department_summary",
    "national_summary",
)


def load_released_tables() -> dict[str, object]:
    """Load canonical tables without running or mutating scientific inputs."""
    configured = os.environ.get("POVERTY_RELEASE_DIR")
    if not configured:
        raise RuntimeError(
            "Set POVERTY_RELEASE_DIR to an immutable directory produced by "
            "`PYTHONPATH=src python -m poverty_pipeline run-lock <lock>` first."
        )
    release_dir = Path(configured).expanduser().resolve(strict=True)
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("release_version"):
        raise ValueError(f"Release manifest has no release_version: {manifest_path}")

    tables: dict[str, object] = {}
    roles = manifest.get("output_roles", {})
    for role in TABLE_ROLES:
        name = roles.get(role)
        if not name:
            continue
        path = release_dir / name
        if path.suffix == ".csv":
            if importlib.util.find_spec("pandas"):
                import pandas
                tables[role] = pandas.read_csv(path)
            else:
                with path.open(newline="", encoding="utf-8") as stream:
                    tables[role] = list(csv.DictReader(stream))
        elif path.suffix == ".parquet":
            if not importlib.util.find_spec("pandas"):
                raise RuntimeError("optional pandas/Parquet engine is unavailable")
            import pandas
            tables[role] = pandas.read_parquet(path)
    if not tables:
        raise FileNotFoundError(f"No released output tables found in {release_dir}")
    return tables
