#!/usr/bin/env python3
"""Materialize governed EPH labor truth and one-dimensional microscope surfaces."""
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
    benchmark_deltas,
    microscope_rows,
    summarize_eph,
    summary_rate_rows,
    summary_stock_rows,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_person_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, low_memory=False)


def run(
    config_path: Path,
    output: Path,
    benchmark_path: Path,
    *,
    max_delta_pp: float,
    allow_partial: bool,
) -> dict[str, object]:
    config = json.loads(config_path.read_text())
    periods = [str(p) for p in config.get("periods", [])]
    parents = config.get("parents") or {}
    mapping = parents.get("eph_person_files") or {}
    if not periods:
        periods = sorted(map(str, mapping))
    missing = [period for period in periods if period not in mapping]
    if missing and not allow_partial:
        raise ValueError(f"missing EPH person parents for configured periods: {missing}")
    selected_periods = [period for period in periods if period in mapping]
    if not selected_periods:
        raise ValueError("no EPH person parents configured")

    benchmark = pd.read_csv(benchmark_path).set_index("period")
    rate_rows: list[dict[str, object]] = []
    stock_rows: list[dict[str, object]] = []
    delta_rows: list[dict[str, object]] = []
    microscope: list[dict[str, object]] = []
    input_files: list[dict[str, object]] = []

    for period in selected_periods:
        path = Path(mapping[period]).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        frame = load_person_file(path)
        summary = summarize_eph(frame)
        rate_rows.extend(summary_rate_rows(period, summary))
        stock_rows.extend(summary_stock_rows(period, summary))
        microscope.extend(microscope_rows(period, frame))
        if period not in benchmark.index:
            raise ValueError(f"official benchmark missing {period}")
        delta_rows.extend(benchmark_deltas(period, summary, benchmark.loc[period]))
        input_files.append(
            {
                "period": period,
                "path": str(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "rows": len(frame),
            }
        )

    output.mkdir(parents=True, exist_ok=False)
    outputs = {
        "labor_rates.csv": pd.DataFrame(rate_rows),
        "labor_stocks.csv": pd.DataFrame(stock_rows),
        "benchmark_deltas.csv": pd.DataFrame(delta_rows),
        "labor_microscope.csv": pd.DataFrame(microscope),
    }
    for name, frame in outputs.items():
        frame.to_csv(output / name, index=False)

    deltas = outputs["benchmark_deltas.csv"]
    max_abs = float(deltas.delta_pp.abs().max())
    failing = deltas[deltas.delta_pp.abs() > max_delta_pp]
    qa = {
        "contract": "research.eph-labor-truth/v1",
        "periods": selected_periods,
        "configured_period_count": len(periods),
        "materialized_period_count": len(selected_periods),
        "missing_periods": missing,
        "benchmark_gate_pp": max_delta_pp,
        "max_abs_benchmark_delta_pp": max_abs,
        "benchmark_gate_status": "PASS" if failing.empty else "FAIL",
        "benchmark_failures": failing.to_dict(orient="records"),
        "scientific_invariants": [
            "EPH official-reproduction rates use PONDERA only",
            "ESTADO 0/1/2/3/4 masses are all retained in QA",
            "unweighted rates are diagnostics only",
            "microscope surfaces are one-dimensional views, not calibration inputs",
            "no Census rows or poverty estimands are modified",
        ],
    }
    (output / "qa.json").write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n")

    manifest = {
        "contract": "research.eph-labor-truth/v1",
        "release_id": output.name,
        "config": {"path": str(config_path.resolve()), "sha256": sha256(config_path)},
        "official_benchmark": {
            "path": str(benchmark_path.resolve()),
            "sha256": sha256(benchmark_path),
        },
        "parents": input_files,
        "artifacts": {
            name: {
                "sha256": sha256(output / name),
                "bytes": (output / name).stat().st_size,
                "rows": len(frame),
            }
            for name, frame in outputs.items()
        },
        "qa": qa,
        "status": qa["benchmark_gate_status"],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    out.add_argument("--config", type=Path, required=True)
    out.add_argument(
        "--benchmark",
        type=Path,
        default=ROOT / "science" / "commissioning" / "benchmarks" / "indec_labor_quarter.csv",
    )
    out.add_argument("--output", type=Path, required=True)
    out.add_argument("--max-delta-pp", type=float, default=0.10)
    out.add_argument("--allow-partial", action="store_true")
    return out


def main() -> int:
    args = parser().parse_args()
    manifest = run(
        args.config,
        args.output,
        args.benchmark,
        max_delta_pp=args.max_delta_pp,
        allow_partial=args.allow_partial,
    )
    print(json.dumps({"release": manifest["release_id"], "status": manifest["status"]}))
    return 0 if manifest["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
