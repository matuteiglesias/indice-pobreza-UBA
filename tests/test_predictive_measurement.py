import math
import unittest

from poverty_pipeline.science.measurement import HouseholdPovertyLines, PersonMember
from poverty_pipeline.science.method import load_poverty_method
from poverty_pipeline.science.predictive_measurement import (
    EmpiricalResidualDistribution,
    PredictiveHouseholdWelfare,
    measure_predictive_poverty,
)


METHOD = "configs/poverty_methods/indec-line-poverty-2016-v1.json"


def brute(location, residuals, line, alpha):
    draws = [max(0.0, location + r) for r in residuals]
    values = []
    for welfare in draws:
        under = welfare <= line
        if alpha == 0:
            values.append(1.0 if under else 0.0)
        elif not under:
            values.append(0.0)
        else:
            values.append(((line - welfare) / line) ** alpha)
    return sum(values) / len(values)


class PredictiveMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.method = load_poverty_method(METHOD)
        self.people = (
            PersonMember("p1", "h1", "male", 30),
            PersonMember("p2", "h1", "female", 30),
        )

    def test_empirical_integration_matches_brute_force_with_zero_floor(self):
        residuals = (-150.0, -80.0, -20.0, 0.0, 60.0, 200.0)
        location = 100.0
        cba_per_ae = 40.0
        cbt_per_ae = 70.0
        result = measure_predictive_poverty(
            self.people,
            (PredictiveHouseholdWelfare("h1", location),),
            (HouseholdPovertyLines("h1", cba_per_ae, cbt_per_ae),),
            self.method,
            EmpiricalResidualDistribution(residuals),
        )
        row = result.households[0]
        cba = row.household_cba
        cbt = row.household_cbt
        for got, line, alpha in (
            (row.indigence_fgt0, cba, 0),
            (row.indigence_fgt1, cba, 1),
            (row.indigence_fgt2, cba, 2),
            (row.poverty_fgt0, cbt, 0),
            (row.poverty_fgt1, cbt, 1),
            (row.poverty_fgt2, cbt, 2),
        ):
            self.assertTrue(math.isclose(got, brute(location, residuals, line, alpha), rel_tol=0, abs_tol=1e-12))

    def test_persons_inherit_expected_household_contributions(self):
        result = measure_predictive_poverty(
            self.people,
            (PredictiveHouseholdWelfare("h1", 100.0),),
            (HouseholdPovertyLines("h1", 40.0, 70.0),),
            self.method,
            EmpiricalResidualDistribution((-100.0, 0.0, 100.0)),
        )
        household = result.households[0]
        self.assertEqual(len(result.persons), 2)
        for person in result.persons:
            self.assertEqual(person.inherited_poverty_fgt0, household.poverty_fgt0)
            self.assertEqual(person.inherited_poverty_fgt1, household.poverty_fgt1)
            self.assertEqual(person.inherited_poverty_fgt2, household.poverty_fgt2)
            self.assertEqual(person.inherited_indigence_fgt0, household.indigence_fgt0)

    def test_poverty_probability_is_not_below_indigence_probability(self):
        result = measure_predictive_poverty(
            self.people,
            (PredictiveHouseholdWelfare("h1", 200.0),),
            (HouseholdPovertyLines("h1", 30.0, 80.0),),
            self.method,
            EmpiricalResidualDistribution((-300.0, -100.0, 0.0, 100.0)),
        )
        row = result.households[0]
        self.assertGreaterEqual(row.poverty_probability, row.indigence_probability)
        self.assertEqual(result.measurement_mode, "predictive_marginal_integrated")
        self.assertEqual(result.uncertainty_status, "not_supplied")


if __name__ == "__main__":
    unittest.main()
