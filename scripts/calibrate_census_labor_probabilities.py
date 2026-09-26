#!/usr/bin/env python3
"""Calibrate raw Census labor probabilities to explicit official domains."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science.labor.core import (  # noqa: E402
    CENSUS_IDENTITY_COLUMNS,
    calibrate_census_domains,
    validate_census_identity,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frame(path: Path, *, domain_column: str) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(
        path,
        dtype={"sample_person_id": str, domain_column: "string"},
        keep_default_na=True,
    )


def run(
    probabilities_path: Path,
    targets_path: Path,
    output: Path,
    *,
    domain_column: str,
) -> dict[str, object]:
    raw = load_frame(probabilities_path, domain_column=domain_column)
    targets = pd.read_csv(targets_path, dtype={domain_column: str})
    identity_audit = validate_census_identity(raw)
    calibrated, qa = calibrate_census_domains(
        raw, targets, domain_col=domain_column
    )

    output.mkdir(parents=True, exist_ok=False)
    probabilities_out = output / "person_labor_probabilities.csv"
    qa_out = output / "calibration_qa.csv"
    calibrated.to_csv(probabilities_out, index=False)
    qa.to_csv(qa_out, index=False)

    calibrated_qa = qa[qa.status == "MODELLED_AND_CALIBRATED"]
    max_delta = 0.0
    if not calibrated_qa.empty:
        max_delta = float(
            calibrated_qa[
                ["activity_delta_pp", "unemployment_delta_pp"]
            ].abs().to_numpy().max()
        )

    manifest = {
        "contract": "research.census-labor-probabilities/v1",
        "release_id": output.name,
        "source_probabilities": {
            "path": str(probabilities_path.resolve()),
            "sha256": sha256(probabilities_path),
        },
        "identity": {
            **identity_audit,
            "preserved_columns": [
                column for column in CENSUS_IDENTITY_COLUMNS if column in calibrated.columns
            ],
        },
        "targets": {
            "path": str(targets_path.resolve()),
            "sha256": sha256(targets_path),
            "domain_column": domain_column,
        },
        "artifacts": {
            probabilities_out.name: {
                "sha256": sha256(probabilities_out),
                "bytes": probabilities_out.stat().st_size,
                "rows": len(calibrated),
            },
            qa_out.name: {
                "sha256": sha256(qa_out),
                "bytes": qa_out.stat().st_size,
                "rows": len(qa),
            },
        },
        "qa": {
            "calibrated_domain_count": int(
                (qa.status == "MODELLED_AND_CALIBRATED").sum()
            ),
            "unbenchmarked_domain_count": int(
                (qa.status == "MODELLED_UNBENCHMARKED").sum()
            ),
            "max_abs_activity_or_unemployment_delta_pp": max_delta,
            "probability_sum_max_abs_error": float(
                (
                    calibrated[["p_employed", "p_unemployed", "p_inactive"]].sum(axis=1)
                    - 1.0
                ).abs().max()
            ),
        },
        "scientific_invariants": [
            "calibration uses no sampler design_inverse_probability_weight",
            "activity and conditional unemployment are calibrated separately",
            "employment is implied and retained as an independent QA check",
            "rows outside an official calibration domain remain modelled but unbenchmarked",
            "no hard synthetic CONDACT state is required",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    out.add_argument("--probabilities", type=Path, required=True)
    out.add_argument("--targets", type=Path, required=True)
    out.add_argument("--output", type=Path, required=True)
    out.add_argument("--domain-column", default="calibration_domain_id")
    return out


def main() -> int:
    args = parser().parse_args()
    manifest = run(
        args.probabilities,
        args.targets,
        args.output,
        domain_column=args.domain_column,
    )
    print(json.dumps({"release": manifest["release_id"], "qa": manifest["qa"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
