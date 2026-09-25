#!/usr/bin/env python3
"""Run the poverty ecosystem commissioning dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from adapters import BENCHMARKS, build_frame
from core import sha256, render_figure


ROOT = Path(__file__).resolve().parent
FIGURE_SPECS = ROOT / "figure_specs.json"


def render_report(status: pd.DataFrame, errors: list[dict[str, str]]) -> str:
    specs = {
        item["id"]: item
        for item in json.loads(FIGURE_SPECS.read_text())["figures"]
    }
    lines = [
        "# Poverty ecosystem commissioning dashboard",
        "",
        "> Research commissioning evidence only; not official INDEC statistics.",
        "",
        "## Figure status",
        "",
        "| # | Figure | Status |",
        "|---|---|---|",
    ]
    for item in status.itertuples():
        lines.append(
            f"| {item.id} | {specs[item.id]['title']} | {item.status} |"
        )
    if errors:
        lines += ["", "## Adapter warnings/errors", ""]
        lines += [
            f"- **{item['adapter']}** — {item['error']}"
            for item in errors
        ]
    lines += [
        "",
        "Every ready PNG has a tidy CSV companion containing exactly the plotted rows.",
        "The diagnostic frame and figures are downstream evidence and must never be used as poverty-estimation parent inputs.",
    ]
    return "\n".join(lines) + "\n"


def run(config_path: Path, output: Path) -> dict[str, object]:
    config = json.loads(config_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)

    frame, parents, errors = build_frame(config)
    frame.to_csv(output / "diagnostic_frame.csv", index=False)

    specs = json.loads(FIGURE_SPECS.read_text())["figures"]
    statuses = [render_figure(spec, frame, figures) for spec in specs]
    status_frame = pd.DataFrame(statuses)
    status_frame.to_csv(output / "figure_status.csv", index=False)

    benchmark_files = [
        BENCHMARKS / "indec_poverty_semester.csv",
        BENCHMARKS / "indec_labor_quarter.csv",
        BENCHMARKS / "sources.json",
    ]
    manifest = {
        "schema_version": "poverty-commissioning-run/v1",
        "status": "RESEARCH_COMMISSIONING_NOT_OFFICIAL_STATISTICS",
        "config": {
            "path": str(config_path.resolve()),
            "sha256": sha256(config_path),
        },
        "figure_specs_sha256": sha256(FIGURE_SPECS),
        "benchmarks": {
            path.name: {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in benchmark_files
        },
        "parents": parents,
        "adapter_errors": errors,
        "diagnostic_rows": int(len(frame)),
        "figures": statuses,
        "ready_figure_count": sum(
            item["status"] == "ready" for item in statuses
        ),
        "blocked_figure_count": sum(
            item["status"] == "blocked_missing_parent"
            for item in statuses
        ),
        "scientific_invariants": [
            "no new poverty estimands",
            "no model fitting or calibration",
            "no duplicated poverty measurement",
            "external benchmarks are validation-only and never estimator parents",
            "every ready plot exports PNG plus plotted-data CSV",
        ],
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output / "report.md").write_text(
        render_report(status_frame, errors)
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = parser().parse_args()
    manifest = run(args.config, args.output)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "diagnostic_rows": manifest["diagnostic_rows"],
                "ready_figure_count": manifest["ready_figure_count"],
                "blocked_figure_count": manifest["blocked_figure_count"],
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
