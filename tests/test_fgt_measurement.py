from __future__ import annotations

import math
import unittest

from poverty_pipeline.science.measurement import (
    HouseholdPovertyLines,
    HouseholdWelfare,
    MeasurementError,
    PersonMember,
    measure_poverty,
)
from poverty_pipeline.science.method import load_poverty_method


METHOD = load_poverty_method("configs/poverty_methods/indec-line-poverty-2016-v1.json")


class PureFGTMeasurementTests(unittest.TestCase):
    def test_official_example_household_adult_equivalents_and_known_fgt(self):
        persons = [
            PersonMember("p1", "h1", "female", 35),
            PersonMember("p2", "h1", "male", 18),
            PersonMember("p3", "h1", "female", 61),
        ]
        result = measure_poverty(
            persons,
            [HouseholdWelfare("h1", 246.0)],
            [HouseholdPovertyLines("h1", 100.0, 200.0)],
            METHOD,
        )
        household = result.households[0]
        self.assertTrue(math.isclose(household.adult_equivalents, 2.46))
        self.assertTrue(math.isclose(household.household_cba, 246.0))
        self.assertTrue(math.isclose(household.household_cbt, 492.0))
        self.assertTrue(household.indigent)
        self.assertTrue(household.poor)
        self.assertEqual(household.indigence_fgt0, 1.0)
        self.assertEqual(household.indigence_fgt1, 0.0)
        self.assertEqual(household.indigence_fgt2, 0.0)
        self.assertTrue(math.isclose(household.poverty_fgt1, 0.5))
        self.assertTrue(math.isclose(household.poverty_fgt2, 0.25))
        self.assertEqual(household.indigence_monetary_shortfall, 0.0)
        self.assertTrue(math.isclose(household.poverty_monetary_shortfall, 246.0))

    def test_second_official_example_sums_to_3_25_adult_equivalents(self):
        persons = [
            PersonMember("m", "h", "male", 40),
            PersonMember("f", "h", "female", 40),
            PersonMember("c5", "h", "female", 5),
            PersonMember("c3", "h", "male", 3),
            PersonMember("c1", "h", "female", 1),
        ]
        result = measure_poverty(
            persons,
            [HouseholdWelfare("h", 1000.0)],
            [HouseholdPovertyLines("h", 100.0, 200.0)],
            METHOD,
        )
        self.assertTrue(math.isclose(result.households[0].adult_equivalents, 3.25))

    def test_zero_welfare_has_unit_normalized_shortfall(self):
        result = measure_poverty(
            [PersonMember("p", "h", "male", 40)],
            [HouseholdWelfare("h", 0.0)],
            [HouseholdPovertyLines("h", 100.0, 200.0)],
            METHOD,
        )
        household = result.households[0]
        self.assertEqual(
            (household.indigence_fgt0, household.indigence_fgt1, household.indigence_fgt2),
            (1.0, 1.0, 1.0),
        )
        self.assertEqual(
            (household.poverty_fgt0, household.poverty_fgt1, household.poverty_fgt2),
            (1.0, 1.0, 1.0),
        )

    def test_welfare_above_cbt_has_zero_contributions(self):
        result = measure_poverty(
            [PersonMember("p", "h", "male", 40)],
            [HouseholdWelfare("h", 201.0)],
            [HouseholdPovertyLines("h", 100.0, 200.0)],
            METHOD,
        )
        household = result.households[0]
        self.assertFalse(household.indigent)
        self.assertFalse(household.poor)
        self.assertEqual(household.poverty_fgt0, 0.0)
        self.assertEqual(household.poverty_fgt1, 0.0)
        self.assertEqual(household.poverty_fgt2, 0.0)
        self.assertEqual(household.poverty_monetary_shortfall, 0.0)

    def test_persons_inherit_household_contributions_explicitly(self):
        result = measure_poverty(
            [
                PersonMember("p1", "h", "male", 40),
                PersonMember("p2", "h", "female", 40),
            ],
            [HouseholdWelfare("h", 100.0)],
            [HouseholdPovertyLines("h", 100.0, 200.0)],
            METHOD,
        )
        household = result.households[0]
        self.assertEqual(len(result.persons), 2)
        for person in result.persons:
            self.assertEqual(person.poor, household.poor)
            self.assertEqual(person.indigent, household.indigent)
            self.assertEqual(person.inherited_poverty_fgt0, household.poverty_fgt0)
            self.assertEqual(person.inherited_poverty_fgt1, household.poverty_fgt1)
            self.assertEqual(person.inherited_poverty_fgt2, household.poverty_fgt2)

    def test_cba_above_cbt_is_rejected(self):
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "h", "male", 40)],
                [HouseholdWelfare("h", 100.0)],
                [HouseholdPovertyLines("h", 300.0, 200.0)],
                METHOD,
            )

    def test_negative_or_nonfinite_scientific_values_are_rejected(self):
        for welfare in (-1.0, float("nan"), float("inf")):
            with self.subTest(welfare=welfare), self.assertRaises(MeasurementError):
                measure_poverty(
                    [PersonMember("p", "h", "male", 40)],
                    [HouseholdWelfare("h", welfare)],
                    [HouseholdPovertyLines("h", 100.0, 200.0)],
                    METHOD,
                )

    def test_duplicate_person_or_household_keys_fail_closed(self):
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [
                    PersonMember("p", "h", "male", 40),
                    PersonMember("p", "h", "female", 30),
                ],
                [HouseholdWelfare("h", 100.0)],
                [HouseholdPovertyLines("h", 100.0, 200.0)],
                METHOD,
            )
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "h", "male", 40)],
                [HouseholdWelfare("h", 100.0), HouseholdWelfare("h", 101.0)],
                [HouseholdPovertyLines("h", 100.0, 200.0)],
                METHOD,
            )

    def test_orphans_empty_households_and_line_coverage_fail_closed(self):
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "missing", "male", 40)],
                [HouseholdWelfare("h", 100.0)],
                [HouseholdPovertyLines("h", 100.0, 200.0)],
                METHOD,
            )
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "h1", "male", 40)],
                [HouseholdWelfare("h1", 100.0), HouseholdWelfare("h2", 100.0)],
                [
                    HouseholdPovertyLines("h1", 100.0, 200.0),
                    HouseholdPovertyLines("h2", 100.0, 200.0),
                ],
                METHOD,
            )
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "h", "male", 40)],
                [HouseholdWelfare("h", 100.0)],
                [HouseholdPovertyLines("other", 100.0, 200.0)],
                METHOD,
            )

    def test_unsupported_demographic_domain_is_a_measurement_error(self):
        with self.assertRaises(MeasurementError):
            measure_poverty(
                [PersonMember("p", "h", "unknown", 40)],
                [HouseholdWelfare("h", 100.0)],
                [HouseholdPovertyLines("h", 100.0, 200.0)],
                METHOD,
            )


if __name__ == "__main__":
    unittest.main()
