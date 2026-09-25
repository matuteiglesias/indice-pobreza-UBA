from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

MODULE_PATH = Path(__file__).parents[1] / "science" / "telescope_b" / "run.py"
SPEC = importlib.util.spec_from_file_location("telescope_b_run", MODULE_PATH)
assert SPEC and SPEC.loader
TB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TB
SPEC.loader.exec_module(TB)


def telescope_a_frame():
    return pd.DataFrame([
        {"household_id":"2024:3:A:1","member_count_records":2,"ITF":100,"sum_P47T":100,"P47T_complete":True,"PONDIH":10,"household_cba":80,"household_cbt":150},
        {"household_id":"2024:3:B:1","member_count_records":1,"ITF":200,"sum_P47T":200,"P47T_complete":True,"PONDIH":20,"household_cba":100,"household_cbt":180},
        {"household_id":"2024:3:C:1","member_count_records":1,"ITF":50,"sum_P47T":50,"P47T_complete":True,"PONDIH":30,"household_cba":100,"household_cbt":180},
    ])


def person_frame():
    return pd.DataFrame([
        {"CODUSU":"A","NRO_HOGAR":"1","COMPONENTE":"1","ANO4":"2024","TRIMESTRE":"3","P47T":"40"},
        {"CODUSU":"A","NRO_HOGAR":"1","COMPONENTE":"2","ANO4":"2024","TRIMESTRE":"3","P47T":"60"},
        {"CODUSU":"B","NRO_HOGAR":"1","COMPONENTE":"1","ANO4":"2024","TRIMESTRE":"3","P47T":"200"},
        {"CODUSU":"C","NRO_HOGAR":"1","COMPONENTE":"1","ANO4":"2024","TRIMESTRE":"3","P47T":"50"},
    ])


def oof_frame():
    return pd.DataFrame([
        {"row_id":"A:1:1","fold":0,"pred":20.0},
        {"row_id":"A:1:2","fold":0,"pred":40.0},
        {"row_id":"B:1:1","fold":1,"pred":220.0},
        {"row_id":"C:1:1","fold":0,"pred":150.0},
    ])


def residual_frame():
    return pd.DataFrame([
        {"outer_fold":0,"residual":-100.0},
        {"outer_fold":0,"residual":0.0},
        {"outer_fold":0,"residual":100.0},
        {"outer_fold":1,"residual":-20.0},
        {"outer_fold":1,"residual":0.0},
        {"outer_fold":1,"residual":20.0},
    ])


class TelescopeBTests(unittest.TestCase):
    def build(self):
        return TB.build_telescope_b(
            telescope_a_frame(), person_frame(), oof_frame(), residual_frame(),
            calibration_bins=2,
        )

    def test_b0_identity_and_no_monetary_scalar(self):
        microscope, _, _, _, _, summary = self.build()
        self.assertEqual(summary["b0_identity"]["households"], 3)
        self.assertEqual(summary["b0_identity"]["persons"], 4)
        self.assertEqual(
            summary["b0_identity"]["monetary_reference"],
            "unchanged Q3 nominal source units; no scalar applied",
        )
        self.assertEqual(
            microscope.set_index("household_id").loc["2024:3:A:1","point_welfare"],
            60.0,
        )

    def test_b1_states_and_fold_specific_predictive_probabilities(self):
        microscope, bridge, *_ = self.build()
        by = microscope.set_index("household_id")
        self.assertEqual(by.loc["2024:3:A:1","observed_state"], "poor_non_indigent")
        self.assertEqual(by.loc["2024:3:A:1","point_state"], "indigent")
        self.assertAlmostEqual(by.loc["2024:3:A:1","p_indigent"], 2/3)
        self.assertAlmostEqual(by.loc["2024:3:B:1","p_poor"], 0.0)
        for universe in ("households","persons"):
            for stage in ("OBSERVED","OOF_POINT","PREDICTIVE"):
                rows = bridge[(bridge.universe == universe)&(bridge.stage == stage)]
                self.assertAlmostEqual(rows.estimate.sum(), 1.0)

    def test_b2_flow_identity(self):
        _, _, flows, *_ = self.build()
        row = flows[(flows.universe == "households")&(flows.concept == "indigence")].iloc[0]
        self.assertAlmostEqual(row.point_rate, 1/6)
        self.assertAlmostEqual(row.predictive_rate, 5/18)
        self.assertAlmostEqual(row.downward_crossing, 1/6)
        self.assertAlmostEqual(row.upward_crossing, 1/18)
        self.assertAlmostEqual(
            row.net_predictive_minus_point,
            row.downward_crossing-row.upward_crossing,
        )
        self.assertAlmostEqual(row.identity_error, 0.0)

    def test_observed_point_transition_matrix_reconciles(self):
        _, _, _, transitions, *_ = self.build()
        for universe in ("households","persons"):
            rows = transitions[transitions.universe == universe]
            self.assertAlmostEqual(rows.weighted_share.sum(), 1.0)
        row = transitions[
            (transitions.universe == "households")
            &(transitions.observed_state == "poor_non_indigent")
            &(transitions.point_state == "indigent")
        ].iloc[0]
        self.assertEqual(row.household_count, 1)
        self.assertEqual(row.weighted_mass, 10.0)

    def test_missing_oof_person_fails_closed(self):
        with self.assertRaisesRegex(TB.TelescopeBError, "OOF predictions do not exactly cover"):
            TB.build_telescope_b(
                telescope_a_frame(), person_frame(), oof_frame().iloc[:-1],
                residual_frame(),
            )

    def test_global_residual_substitution_cannot_cover_all_outer_folds(self):
        bad = residual_frame()[residual_frame().outer_fold == 0]
        with self.assertRaisesRegex(TB.TelescopeBError, "missing nested residual ECDF folds"):
            TB.build_telescope_b(
                telescope_a_frame(), person_frame(), oof_frame(), bad,
            )


if __name__ == "__main__":
    unittest.main()
