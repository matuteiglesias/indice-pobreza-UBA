import unittest

from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    HouseholdDomain,
    HouseholdWeight,
)
from poverty_pipeline.predictive_estimation_v2 import estimate_predictive_poverty
from poverty_pipeline.science.measurement import HouseholdPovertyLines, PersonMember
from poverty_pipeline.science.method import load_poverty_method
from poverty_pipeline.science.predictive_measurement import (
    EmpiricalResidualDistribution,
    PredictiveHouseholdWelfare,
    measure_predictive_poverty,
)


class PredictiveEstimationV2Test(unittest.TestCase):
    def test_unit_weight_national_reconciliation(self):
        method = load_poverty_method("configs/poverty_methods/indec-line-poverty-2016-v1.json")
        persons = (
            PersonMember("p1", "h1", "male", 30),
            PersonMember("p2", "h2", "female", 30),
        )
        measurement = measure_predictive_poverty(
            persons,
            (
                PredictiveHouseholdWelfare("h1", 100.0),
                PredictiveHouseholdWelfare("h2", 300.0),
            ),
            (
                HouseholdPovertyLines("h1", 50.0, 100.0),
                HouseholdPovertyLines("h2", 50.0, 100.0),
            ),
            method,
            EmpiricalResidualDistribution((-100.0, 0.0, 100.0)),
        )
        domains = (
            HouseholdDomain("h1", "department_2010", "d1"),
            HouseholdDomain("h2", "department_2010", "d2"),
        )
        design = EstimationDesign(
            "unit_weight_target_year_sample_research_v1",
            "unit weight over target-year-shaped research sample",
            (HouseholdWeight("h1", 1.0), HouseholdWeight("h2", 1.0)),
        )
        result = estimate_predictive_poverty(
            measurement,
            domains,
            design,
            EstimationContext("predictive-test", "2024-Q3", "2010"),
        )
        national = [
            row for row in result.estimates
            if row.universe == "households"
            and row.geography_level == "national"
            and row.concept == "poverty"
            and row.estimand == "fgt0"
        ]
        self.assertEqual(len(national), 1)
        expected = sum(row.poverty_fgt0 for row in measurement.households) / 2
        self.assertAlmostEqual(national[0].estimate, expected)
        self.assertEqual(result.qa.national_reconciliation, "passed")
        self.assertEqual(result.qa.uncertainty_status, "not_supplied")
        self.assertEqual(result.qa.min_analysis_weight, 1.0)
        self.assertEqual(result.qa.max_analysis_weight, 1.0)


if __name__ == "__main__":
    unittest.main()
