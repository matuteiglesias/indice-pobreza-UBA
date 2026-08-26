from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from poverty_pipeline.science.method import (
    MethodContractError,
    load_poverty_method,
    poverty_method_from_dict,
)


METHOD_PATH = Path("configs/poverty_methods/indec-line-poverty-2016-v1.json")


class PovertyMethodContractTests(unittest.TestCase):
    def setUp(self):
        self.method = load_poverty_method(METHOD_PATH)
        self.document = json.loads(METHOD_PATH.read_text(encoding="utf-8"))

    def test_identity_and_fixed_semantics(self):
        self.assertEqual(
            self.method.release_id,
            "argentina.indec-line-poverty-2016@v1",
        )
        self.assertEqual(self.method.welfare_entity, "household")
        self.assertEqual(self.method.welfare_transform, "linear_currency")
        self.assertEqual(self.method.comparison, "at_or_below")
        self.assertEqual(self.method.person_inheritance, "inherits_household_status")
        self.assertEqual(self.method.fgt_alphas, (0, 1, 2))

    def test_published_adult_equivalence_examples(self):
        self.assertEqual(self.method.adult_equivalence(sex="female", age=35), 0.77)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=18), 1.02)
        self.assertEqual(self.method.adult_equivalence(sex="female", age=61), 0.67)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=40), 1.00)
        self.assertEqual(self.method.adult_equivalence(sex="female", age=5), 0.60)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=1), 0.37)

    def test_age_75_76_boundary_matches_current_indec_table(self):
        self.assertEqual(self.method.adult_equivalence(sex="female", age=75), 0.67)
        self.assertEqual(self.method.adult_equivalence(sex="female", age=76), 0.63)
        self.assertEqual(self.method.adult_equivalence(sex="female", age=110), 0.63)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=75), 0.83)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=76), 0.74)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=110), 0.74)

    def test_under_one_year_operational_age_value(self):
        self.assertEqual(self.method.adult_equivalence(sex="female", age=0), 0.35)
        self.assertEqual(self.method.adult_equivalence(sex="male", age=0), 0.35)

    def test_unknown_demographic_domain_fails_closed(self):
        with self.assertRaises(MethodContractError):
            self.method.adult_equivalence(sex="unknown", age=30)
        with self.assertRaises(MethodContractError):
            self.method.adult_equivalence(sex="female", age=-1)
        with self.assertRaises(MethodContractError):
            self.method.adult_equivalence(sex="female", age=True)

    def test_comparison_is_not_a_free_switch(self):
        document = copy.deepcopy(self.document)
        document["thresholds"]["comparison"] = "below"
        with self.assertRaises(MethodContractError):
            poverty_method_from_dict(document)

    def test_adult_equivalence_gaps_are_rejected(self):
        document = copy.deepcopy(self.document)
        female_76 = next(
            cell for cell in document["adult_equivalence"]["cells"]
            if cell["sex"] == "female" and cell["age_min"] == 76
        )
        female_76["age_min"] = 77
        with self.assertRaises(MethodContractError):
            poverty_method_from_dict(document)

    def test_terminal_band_must_be_open_ended(self):
        document = copy.deepcopy(self.document)
        male_terminal = next(
            cell for cell in document["adult_equivalence"]["cells"]
            if cell["sex"] == "male" and cell["age_min"] == 76
        )
        male_terminal["age_max"] = 110
        with self.assertRaises(MethodContractError):
            poverty_method_from_dict(document)

    def test_fgt_contract_is_fixed_to_zero_one_two(self):
        document = copy.deepcopy(self.document)
        document["estimands"]["fgt_alphas"] = [0, 1]
        with self.assertRaises(MethodContractError):
            poverty_method_from_dict(document)


if __name__ == "__main__":
    unittest.main()
