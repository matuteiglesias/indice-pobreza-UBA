from __future__ import annotations

import importlib.util
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


    def test_adaptive_renderers_materialize_single_period_diagnostics(self):
        module_path = ROOT / "science" / "commissioning" / "core.py"
        spec = importlib.util.spec_from_file_location("commissioning_core", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)

        rows = []
        # Basket mechanics: positive nominal levels spanning orders of magnitude.
        for period, scale in (("2019-01", 1.0), ("2025-01", 40.0)):
            for region, factor in (("pampeana", 1.0), ("patagonia", 1.15)):
                rows.append(core.make_row(
                    period, "basket_level", f"cba:{region}", 10_000 * scale * factor,
                    "ARS_per_adult_equivalent", geography_level="poverty_region",
                    geography_id=region, source_role="test", parent_id="basket",
                ))
                rows.append(core.make_row(
                    period, "basket_level", f"cbt:{region}", 24_000 * scale * factor,
                    "ARS_per_adult_equivalent", geography_level="poverty_region",
                    geography_id=region, source_role="test", parent_id="basket",
                ))
                rows.append(core.make_row(
                    period, "basket_ratio", f"cbt_over_cba:{region}", 2.4,
                    "ratio", geography_level="poverty_region", geography_id=region,
                    source_role="test", parent_id="basket",
                ))

        # One-period cross-sectional renderers.
        for stage, values in {
            "observed": [0.45, 0.75, 1.30, 2.10, 3.40],
            "point": [0.55, 0.85, 1.38, 2.08, 2.95],
        }.items():
            for q, value in zip(("q10", "q25", "q50", "q75", "q90"), values):
                rows.append(core.make_row(
                    "2024-Q3", "welfare_cbt_ratio_quantile", f"{stage}:{q}", value,
                    "ratio", universe="persons", source_role="test", parent_id="welfare",
                ))

        for concept, values in {
            "poverty": {"0-14": 0.52, "15-29": 0.45, "30-64": 0.34, "65+": 0.15},
            "indigence": {"0-14": 0.13, "15-29": 0.12, "30-64": 0.08, "65+": 0.025},
        }.items():
            for age_group, value in values.items():
                rows.append(core.make_row(
                    "2024-Q3", "poverty_rate_age", f"{concept}:{age_group}", value,
                    "proportion", universe="persons", geography_level="age_group",
                    geography_id=age_group, source_role="test", parent_id="age",
                ))

        for concept, values in {
            "poverty": {"cuyo": 0.34, "gran_buenos_aires": 0.38, "noreste": 0.50, "noroeste": 0.42, "pampeana": 0.36, "patagonia": 0.33},
            "indigence": {"cuyo": 0.09, "gran_buenos_aires": 0.08, "noreste": 0.15, "noroeste": 0.09, "pampeana": 0.09, "patagonia": 0.055},
        }.items():
            for region, value in values.items():
                rows.append(core.make_row(
                    "2024-Q3", "poverty_rate_region", f"{concept}:{region}", value,
                    "proportion", universe="persons", geography_level="eph_region",
                    geography_id=region, source_role="test", parent_id="region",
                ))

        for stage, values in {
            "observed": {"poverty": 0.383, "indigence": 0.092},
            "oof_point": {"poverty": 0.328, "indigence": 0.064},
            "predictive": {"poverty": 0.374, "indigence": 0.148},
        }.items():
            for concept, value in values.items():
                rows.append(core.make_row(
                    "2024-Q3", "telescope_b_rate", f"{stage}:{concept}", value,
                    "proportion", universe="persons", source_role="test", parent_id="b",
                ))

        for stage, values in {
            "eph_point": {"poverty": 0.328, "indigence": 0.064},
            "eph_predictive": {"poverty": 0.374, "indigence": 0.148},
            "census_point": {"poverty": 0.472, "indigence": 0.108},
            "census_predictive": {"poverty": 0.487, "indigence": 0.209},
        }.items():
            for concept, value in values.items():
                rows.append(core.make_row(
                    "2024-Q3", "telescope_c_rate", f"{stage}:{concept}", value,
                    "proportion", universe="persons", source_role="test", parent_id="c",
                ))

        frame = core.validate_frame(pd.DataFrame(rows))
        specs = {
            "03": ("basket_engel", "Basket and Engel mechanics"),
            "04": ("income_in_cbt_units", "Household welfare in CBT units"),
            "06": ("poverty_by_age", "Poverty by age"),
            "07": ("poverty_by_region", "Poverty by region"),
            "08": ("telescope_b_bridge", "Telescope B: observed to point to predictive"),
            "09": ("telescope_c_transport", "Telescope C: EPH to Census transport"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for figure_id, (slug, title) in specs.items():
                result = core.render_figure(
                    {"id": figure_id, "slug": slug, "title": title},
                    frame,
                    output,
                )
                self.assertEqual(result["status"], "ready")
                self.assertGreater((output / result["png"]).stat().st_size, 1_000)
                self.assertGreater((output / result["csv"]).stat().st_size, 100)

    def test_poverty_benchmark_has_expected_anchor_values(self):
        frame = pd.read_csv(
            ROOT / "science" / "commissioning" / "benchmarks" / "indec_poverty_semester.csv"
        )
        people = frame[frame.universe == "persons"].set_index(["period", "concept"])
        self.assertAlmostEqual(people.loc[("2022-S1", "poverty"), "rate"], 0.365)
        self.assertEqual(
            int(people.loc[("2022-S2", "indigence"), "count"]),
            2_356_435,
        )
        self.assertAlmostEqual(people.loc[("2023-S2", "poverty"), "rate"], 0.417)
        self.assertEqual(
            int(people.loc[("2023-S1", "poverty"), "count"]),
            11_769_747,
        )
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

    def test_labor_benchmark_spans_sixteen_quarters(self):
        frame = pd.read_csv(
            ROOT / "science" / "commissioning" / "benchmarks" / "indec_labor_quarter.csv"
        )
        self.assertEqual(len(frame), 16)
        self.assertEqual(frame.period.iloc[0], "2022-Q1")
        self.assertEqual(frame.period.iloc[-1], "2025-Q4")
        self.assertAlmostEqual(frame.unemployment_rate.iloc[0], 0.070)
        self.assertAlmostEqual(frame.unemployment_rate.iloc[-1], 0.075)


if __name__ == "__main__":
    unittest.main()
