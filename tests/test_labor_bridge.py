from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science.labor.core import (  # noqa: E402
    LaborContractError,
    benchmark_deltas,
    calibrate_census_domains,
    calibrate_logit_offset,
    microscope_rows,
    summarize_eph,
)


def eph_fixture():
    return pd.DataFrame(
        {
            "ESTADO": [1, 1, 2, 3, 4, 0],
            "PONDERA": [20, 10, 10, 30, 20, 10],
            "AGLOMERADO": [32, 32, 32, 33, 33, 33],
            "CH04": [1, 2, 1, 2, 1, 2],
            "CH06": [44, 33, 26, 72, 8, 50],
            "REGION": [1, 1, 1, 1, 1, 1],
        }
    )


class LaborBridgeTest(unittest.TestCase):
    def test_summary_preserves_complete_estado_accounting_and_headline_identities(self):
        summary = summarize_eph(eph_fixture())
        self.assertEqual(summary.total_weight, 100)
        self.assertEqual(summary.responded_weight, 90)
        self.assertEqual(
            summary.state_weight,
            {0: 10.0, 1: 30.0, 2: 10.0, 3: 30.0, 4: 20.0},
        )
        self.assertAlmostEqual(summary.activity_rate, 0.4)
        self.assertAlmostEqual(summary.employment_rate, 0.3)
        self.assertAlmostEqual(summary.unemployment_rate, 0.25)
        self.assertAlmostEqual(summary.accounting_gap, 0.0)
        self.assertAlmostEqual(
            summary.employment_rate,
            summary.activity_rate * (1 - summary.unemployment_rate),
        )

    def test_benchmark_delta_is_in_percentage_points(self):
        summary = summarize_eph(eph_fixture())
        rows = benchmark_deltas(
            "2025-Q4",
            summary,
            {
                "activity_rate": 0.39,
                "employment_rate": 0.295,
                "unemployment_rate": 0.24,
            },
        )
        by_metric = {row["metric"]: row for row in rows}
        self.assertAlmostEqual(by_metric["activity"]["delta_pp"], 1.0)
        self.assertAlmostEqual(by_metric["employment"]["delta_pp"], 0.5)
        self.assertAlmostEqual(by_metric["unemployment"]["delta_pp"], 1.0)

    def test_microscope_emits_weighted_and_unweighted_rows_without_cross_products(self):
        frame = pd.DataFrame(microscope_rows("2025-Q4", eph_fixture()))
        self.assertTrue(
            {"agglomerate", "region", "sex", "age_group"} <= set(frame.dimension)
        )
        self.assertEqual(set(frame.estimator), {"pondera", "unweighted"})
        self.assertEqual(set(frame.metric), {"activity", "employment", "unemployment"})
        self.assertIn(
            "32",
            set(frame.loc[frame.dimension == "agglomerate", "group_id"]),
        )

    def test_logit_offset_hits_requested_mean(self):
        calibrated, offset = calibrate_logit_offset([0.1, 0.2, 0.4, 0.8], 0.55)
        self.assertAlmostEqual(float(calibrated.mean()), 0.55, places=10)
        self.assertTrue(math.isfinite(offset))
        self.assertTrue(np.all((calibrated > 0) & (calibrated < 1)))

    def test_domain_calibration_hits_activity_and_unemployment_and_preserves_sum(self):
        probabilities = pd.DataFrame(
            {
                "sample_person_id": ["a", "b", "c", "d", "e"],
                "calibration_domain_id": ["32", "32", "33", "33", None],
                "p_active_raw": [0.2, 0.8, 0.4, 0.6, 0.3],
                "p_unemployed_given_active_raw": [0.1, 0.2, 0.3, 0.1, 0.4],
            }
        )
        targets = pd.DataFrame(
            {
                "calibration_domain_id": ["32", "33"],
                "activity_rate": [0.60, 0.50],
                "unemployment_rate": [0.10, 0.20],
                "employment_rate": [0.54, 0.40],
            }
        )
        out, qa = calibrate_census_domains(probabilities, targets)
        self.assertTrue(
            np.allclose(
                out[["p_employed", "p_unemployed", "p_inactive"]].sum(axis=1),
                1.0,
            )
        )
        calibrated = qa[qa.status == "MODELLED_AND_CALIBRATED"].set_index(
            "calibration_domain_id"
        )
        self.assertAlmostEqual(calibrated.loc["32", "activity_rate"], 0.60, places=10)
        self.assertAlmostEqual(
            calibrated.loc["32", "unemployment_rate"], 0.10, places=10
        )
        self.assertAlmostEqual(calibrated.loc["33", "activity_rate"], 0.50, places=10)
        self.assertAlmostEqual(
            calibrated.loc["33", "unemployment_rate"], 0.20, places=10
        )
        outside = out[out.calibration_domain_id.isna()].iloc[0]
        self.assertEqual(outside.calibration_status, "MODELLED_UNBENCHMARKED")
        self.assertAlmostEqual(outside.p_active, outside.p_active_raw)

    def test_domain_calibration_fails_closed_on_missing_target(self):
        probabilities = pd.DataFrame(
            {
                "sample_person_id": ["a"],
                "calibration_domain_id": ["32"],
                "p_active_raw": [0.5],
                "p_unemployed_given_active_raw": [0.1],
            }
        )
        targets = pd.DataFrame(
            {
                "calibration_domain_id": ["33"],
                "activity_rate": [0.5],
                "unemployment_rate": [0.1],
            }
        )
        with self.assertRaisesRegex(LaborContractError, "missing official labor target"):
            calibrate_census_domains(probabilities, targets)


if __name__ == "__main__":
    unittest.main()
