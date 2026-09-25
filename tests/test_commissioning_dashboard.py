from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class CommissioningDashboardTest(unittest.TestCase):
    def test_benchmark_only_run_materializes_three_figures(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "commissioning"
            command = [
                sys.executable,
                str(ROOT / "science" / "commissioning" / "run.py"),
                "--config",
                str(ROOT / "science" / "commissioning" / "config.example.json"),
                "--output",
                str(output),
            ]
            subprocess.run(command, cwd=ROOT, check=True)

            manifest = json.loads((output / "run_manifest.json").read_text())
            self.assertEqual(manifest["ready_figure_count"], 3)
            self.assertEqual(manifest["blocked_figure_count"], 7)
            self.assertEqual(manifest["adapter_errors"], [])

            status = pd.read_csv(output / "figure_status.csv", dtype={"id": str})
            ready = set(status.loc[status.status == "ready", "id"])
            self.assertEqual(ready, {"01", "02", "05"})
            for figure_id, slug in (
                ("01", "headline_poverty"),
                ("02", "people_below_lines"),
                ("05", "labor_market"),
            ):
                self.assertTrue((output / "figures" / f"{figure_id}_{slug}.csv").exists())
                self.assertTrue((output / "figures" / f"{figure_id}_{slug}.png").exists())

    def test_poverty_benchmark_has_expected_anchor_values(self):
        frame = pd.read_csv(
            ROOT / "science" / "commissioning" / "benchmarks" / "indec_poverty_semester.csv"
        )
        people = frame[frame.universe == "persons"].set_index(["period", "concept"])
        self.assertAlmostEqual(people.loc[("2024-S1", "poverty"), "rate"], 0.529)
        self.assertEqual(
            int(people.loc[("2024-S1", "poverty"), "count"]),
            15_685_603,
        )
        self.assertAlmostEqual(people.loc[("2025-S2", "poverty"), "rate"], 0.282)
        self.assertEqual(
            int(people.loc[("2025-S2", "indigence"), "count"]),
            1_884_110,
        )

    def test_labor_benchmark_spans_eight_quarters(self):
        frame = pd.read_csv(
            ROOT / "science" / "commissioning" / "benchmarks" / "indec_labor_quarter.csv"
        )
        self.assertEqual(len(frame), 8)
        self.assertEqual(frame.period.iloc[0], "2024-Q1")
        self.assertEqual(frame.period.iloc[-1], "2025-Q4")
        self.assertAlmostEqual(frame.unemployment_rate.iloc[0], 0.077)
        self.assertAlmostEqual(frame.unemployment_rate.iloc[-1], 0.075)


if __name__ == "__main__":
    unittest.main()
