"""Read-only access to tables emitted by a governed poverty release."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

TABLE_ROLES = (
    "household_classification",
    "department_summary",
    "national_summary",
)


def load_released_tables() -> dict[str, pd.DataFrame]:
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

    tables: dict[str, pd.DataFrame] = {}
    for role in TABLE_ROLES:
        path = release_dir / f"{role}.parquet"
        if path.is_file():
            tables[role] = pd.read_parquet(path)
    if not tables:
        raise FileNotFoundError(f"No released output tables found in {release_dir}")
    return tables
