from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "science" / "telescope_a" / "run.py"
SPEC = importlib.util.spec_from_file_location("telescope_a_run", MODULE_PATH)
assert SPEC and SPEC.loader
TA = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TA
SPEC.loader.exec_module(TA)


REGIONS = ["gran_buenos_aires", "cuyo", "noreste", "noroeste", "pampeana", "patagonia"]


def basket_frame(base: float) -> pd.DataFrame:
    rows = []
    for date, shift in (("2024-07-01", -10), ("2024-08-01", 0), ("2024-09-01", 10)):
        rows.append({"indice_tiempo": date, **{region: str(base + shift) for region in REGIONS}})
    return pd.DataFrame(rows)


def household_frame(*, mismatch: bool = False) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "CODUSU": "A", "NRO_HOGAR": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "REGION": "1", "AGLOMERADO": "32", "IX_TOT": "3" if mismatch else "2",
            "ITF": "300", "IPCF": "150", "PONDIH": "10",
        },
        {
            "CODUSU": "B", "NRO_HOGAR": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "REGION": "40", "AGLOMERADO": "10", "IX_TOT": "1",
            "ITF": "-9", "IPCF": "-9", "PONDIH": "100",
        },
        {
            "CODUSU": "C", "NRO_HOGAR": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "REGION": "40", "AGLOMERADO": "10", "IX_TOT": "1",
            "ITF": "0", "IPCF": "0", "PONDIH": "20",
        },
    ])


def person_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "CODUSU": "A", "NRO_HOGAR": "1", "COMPONENTE": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "CH04": "1", "CH06": "40", "P47T": "100",
        },
        {
            "CODUSU": "A", "NRO_HOGAR": "1", "COMPONENTE": "2", "ANO4": "2024", "TRIMESTRE": "3",
            "CH04": "2", "CH06": "35", "P47T": "200",
        },
        {
            "CODUSU": "B", "NRO_HOGAR": "1", "COMPONENTE": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "CH04": "1", "CH06": "40", "P47T": "-9",
        },
        {
            "CODUSU": "C", "NRO_HOGAR": "1", "COMPONENTE": "1", "ANO4": "2024", "TRIMESTRE": "3",
            "CH04": "1", "CH06": "40", "P47T": "0",
        },
    ])


class TelescopeAT0T2Tests(unittest.TestCase):
    def test_valid_itf_zero_pondih_remains_source_diagnostic_but_not_a0(self):
        households = household_frame()
        households.loc[households.CODUSU == "C", "PONDIH"] = "0"
        microscope, summary = TA.build_telescope(households, person_frame(), basket_frame(100.0), basket_frame(200.0))
        self.assertEqual(microscope.household_id.tolist(), ["2024:3:A:1"])
        self.assertEqual(summary["source_universe"]["zero_pondih_households"], 1)
        self.assertEqual(summary["a0_universe"]["households"], 1)
        self.assertEqual(summary["a0_universe"]["reason"], "income-estimation support under the source PONDIH design")

    def test_t3_stage_seams_preserve_the_declared_axes(self):
        people = person_frame()
        # A is incomplete but remains in A0 because its ITF is valid.
        people.loc[(people.CODUSU == "A") & (people.COMPONENTE == "2"), "P47T"] = "-9"
        microscope, summary = TA.build_telescope(household_frame(), people, basket_frame(100.0), basket_frame(200.0))
        stages = summary["waterfall"]["stages"]
        self.assertEqual(stages["A0_DIRECT"]["household_count"], 2)
        self.assertEqual(stages["A1_COMPLETE"]["household_count"], 1)
        self.assertEqual(stages["A1_COMPLETE"]["welfare_semantics"], "ITF")
        self.assertEqual(stages["A2_RECONSTRUCTED"]["household_count"], stages["A1_COMPLETE"]["household_count"])
        self.assertEqual(stages["A2_RECONSTRUCTED"]["welfare_semantics"], "sum_P47T")
        self.assertEqual(stages["A3_UNWEIGHTED"]["weight_semantics"], "unit")
        selection = summary["waterfall"]["selection_diagnostics"]
        self.assertEqual(selection["removed_household_count"], 1)
        self.assertEqual(selection["a0_household_count"], selection["a1_household_count"] + selection["removed_household_count"])

    def test_t3_equal_reconstruction_and_equal_weights_have_zero_deltas(self):
        microscope, summary = TA.build_telescope(household_frame(), person_frame(), basket_frame(100.0), basket_frame(200.0))
        deltas = summary["waterfall"]["deltas"]
        self.assertTrue(all(value == 0.0 for value in deltas["A2_minus_A1"].values()))
        # The fixture has unequal PONDIH, so this also proves A3 is a distinct estimator run.
        self.assertTrue(any(value != 0.0 for value in deltas["A3_minus_A2"].values()))
    def test_period_is_part_of_household_identity(self):
        rows = pd.DataFrame([
            {"ANO4": "2024", "TRIMESTRE": "3", "CODUSU": "A", "NRO_HOGAR": "1"},
            {"ANO4": "2024", "TRIMESTRE": "4", "CODUSU": "A", "NRO_HOGAR": "1"},
        ])
        self.assertEqual(TA._household_ids(rows).tolist(), ["2024:3:A:1", "2024:4:A:1"])

    def test_q3_microscope_keeps_zero_itf_excludes_minus9_and_reconciles_pondih(self):
        microscope, summary = TA.build_telescope(
            household_frame(),
            person_frame(),
            basket_frame(100.0),
            basket_frame(200.0),
            period="2024-Q3",
        )

        self.assertEqual(microscope.household_id.tolist(), ["2024:3:A:1", "2024:3:C:1"])
        self.assertEqual(microscope.ITF.tolist(), [300.0, 0.0])
        self.assertTrue(microscope.P47T_complete.all())
        self.assertTrue((microscope.itf_minus_sum_p47t == 0).all())
        self.assertTrue((microscope.ipcf_delta == 0).all())

        a = microscope.set_index("household_id").loc["2024:3:A:1"]
        c = microscope.set_index("household_id").loc["2024:3:C:1"]
        self.assertAlmostEqual(a.adult_equivalents, 1.77)
        self.assertFalse(bool(a.indigent))
        self.assertTrue(bool(a.poor))
        self.assertTrue(bool(a.poor_non_indigent))
        self.assertTrue(bool(c.indigent))
        self.assertTrue(bool(c.poor))

        retention = summary["source_retention"]
        self.assertEqual(retention["raw_households"], 3)
        self.assertEqual(retention["retained_valid_itf_households"], 2)
        self.assertEqual(retention["excluded_invalid_itf_households"], 1)
        self.assertEqual(retention["raw_positive_pondih_mass"], 130.0)
        self.assertEqual(retention["retained_pondih_mass"], 30.0)

        denom = summary["denominator_reconciliation"]
        self.assertEqual(denom["expected_household_sum_pondih"], 30.0)
        self.assertEqual(denom["estimator_household_denominator"], 30.0)
        self.assertEqual(denom["expected_person_sum_pondih_times_members"], 40.0)
        self.assertEqual(denom["estimator_person_denominator"], 40.0)
        self.assertEqual(denom["status"], "passed")

        national = {
            (row["universe"], row["concept"], row["estimand"]): row["estimate"]
            for row in summary["national_estimates"]
        }
        self.assertAlmostEqual(national[("households", "poverty", "fgt0")], 1.0)
        self.assertAlmostEqual(national[("persons", "poverty", "fgt0")], 1.0)
        self.assertAlmostEqual(national[("households", "indigence", "fgt0")], 2 / 3)
        self.assertAlmostEqual(national[("persons", "indigence", "fgt0")], 0.5)

    def test_p47t_incompleteness_is_diagnostic_not_a_welfare_redefinition(self):
        people = person_frame()
        people.loc[(people.CODUSU == "A") & (people.COMPONENTE == "2"), "P47T"] = "-9"
        microscope, summary = TA.build_telescope(
            household_frame(), people, basket_frame(100.0), basket_frame(200.0), period="2024-Q3"
        )
        a = microscope.set_index("household_id").loc["2024:3:A:1"]
        self.assertFalse(bool(a.P47T_complete))
        self.assertTrue(pd.isna(a.sum_P47T))
        self.assertEqual(a.ITF, 300.0)
        self.assertTrue(bool(a.poor))
        self.assertEqual(summary["accounting"]["p47t_complete_households"], 1)

    def test_membership_mismatch_fails_closed(self):
        with self.assertRaisesRegex(TA.TelescopeAError, "membership mismatch"):
            TA.build_telescope(
                household_frame(mismatch=True),
                person_frame(),
                basket_frame(100.0),
                basket_frame(200.0),
                period="2024-Q3",
            )

    def test_basket_requires_all_three_requested_months(self):
        cba = basket_frame(100.0).iloc[:2].copy()
        with self.assertRaisesRegex(TA.TelescopeAError, "each requested month exactly once"):
            TA.build_telescope(
                household_frame(),
                person_frame(),
                cba,
                basket_frame(200.0),
                period="2024-Q3",
            )


if __name__ == "__main__":
    unittest.main()
