#!/usr/bin/env python3
"""Build period-specific L3 calibration targets from governed EPH labor truth."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science.labor.core import calibration_targets_from_microscope  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--microscope", type=Path, required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    microscope = pd.read_csv(args.microscope, dtype={"group_id": str})
    targets = calibration_targets_from_microscope(microscope, args.period)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    targets.to_csv(args.output, index=False)
    manifest = {
        "contract": "research.eph-labor-calibration-targets/v1",
        "period": args.period,
        "source_microscope": {
            "path": str(args.microscope.resolve()),
            "sha256": sha256(args.microscope),
        },
        "artifact": {
            "path": str(args.output.resolve()),
            "sha256": sha256(args.output),
            "rows": len(targets),
        },
        "semantics": (
            "PONDERA-weighted native EPH agglomerate A/E/U; "
            "national official benchmark remains validation-only"
        ),
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"period": args.period, "domains": len(targets), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
