from dataclasses import replace
import unittest

from poverty_pipeline.contracts_v2 import prepare_measurement_inputs
from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    EstimationError,
    HouseholdDomain,
    HouseholdWeight,
    estimate_poverty,
)
from poverty_pipeline.science import load_poverty_method, measure_poverty
from tests.test_contracts_v2 import fixture_inputs


class V2EstimationTest(unittest.TestCase):
    def setUp(self):
        method = load_poverty_method("configs/poverty_methods/indec-line-poverty-2016-v1.json")
        frame, welfare, lines, binding = fixture_inputs()
        prepared = prepare_measurement_inputs(
            frame, welfare, lines, binding, method, estimation_period="2024-Q1"
        )
        self.measurement = measure_poverty(
            prepared.persons, prepared.household_welfare, prepared.household_lines, method
        )
        self.frame = frame
        self.domains = tuple(
            HouseholdDomain(h.household_id, "department_2010", h.department_2010_id)
            for h in frame.households
        )
        self.design = EstimationDesign(
            design_id="cpv2010-frame-ipw-fixture",
            weight_semantics=frame.weight_semantics,
            weights=tuple(HouseholdWeight(h.household_id, h.analysis_weight) for h in frame.households),
        )
        self.context = EstimationContext(
            release_id="poverty-estimate-fixture-v2",
            estimation_period="2024-Q1",
            frame_vintage=frame.frame_vintage,
        )

    def test_estimates_fgt_for_households_persons_domains_and_national(self):
        result = estimate_poverty(self.measurement, self.domains, self.design, self.context)
        self.assertEqual(len(result.estimates), 36)
        self.assertEqual(result.qa.domain_count, 2)
        self.assertEqual(result.qa.household_rows, 3)
        self.assertEqual(result.qa.person_rows, 4)
        self.assertEqual(result.qa.uncertainty_status, "not_supplied")
        self.assertTrue(all(row.estimand in {"fgt0", "fgt1", "fgt2"} for row in result.estimates))
        self.assertTrue(all(row.uncertainty_status == "not_supplied" for row in result.estimates))

    def test_person_and_household_weight_denominators_differ_as_expected(self):
        result = estimate_poverty(self.measurement, self.domains, self.design, self.context)
        household = next(row for row in result.estimates
                         if row.universe == "households" and row.geography_level == "national"
                         and row.concept == "poverty" and row.estimand == "fgt0")
        person = next(row for row in result.estimates
                      if row.universe == "persons" and row.geography_level == "national"
                      and row.concept == "poverty" and row.estimand == "fgt0")
        self.assertEqual(household.weighted_denominator, 19.0)
        self.assertEqual(person.weighted_denominator, 29.0)
        self.assertEqual(household.estimate, 1.0)
        self.assertEqual(person.estimate, 1.0)

    def test_national_rows_reconcile_to_declared_domain_rows(self):
        result = estimate_poverty(self.measurement, self.domains, self.design, self.context)
        for national in [r for r in result.estimates if r.geography_level == "national"]:
            children = [r for r in result.estimates
                        if r.geography_level == "department_2010"
                        and r.universe == national.universe and r.concept == national.concept
                        and r.estimand == national.estimand]
            self.assertAlmostEqual(
                national.weighted_numerator,
                sum(r.weighted_numerator for r in children),
            )
            self.assertAlmostEqual(
                national.weighted_denominator,
                sum(r.weighted_denominator for r in children),
            )

    def test_estimator_is_not_hardcoded_to_department(self):
        zones = tuple(
            HouseholdDomain(h.household_id, "research_zone", "zone-a" if h.household_id != "h3" else "zone-b")
            for h in self.frame.households
        )
        result = estimate_poverty(self.measurement, zones, self.design, self.context)
        self.assertEqual(result.qa.domain_count, 2)
        self.assertEqual(
            {r.geography_level for r in result.estimates if r.geography_level != "national"},
            {"research_zone"},
        )

    def test_missing_domain_fails_closed(self):
        with self.assertRaisesRegex(EstimationError, "exactly cover"):
            estimate_poverty(self.measurement, self.domains[:-1], self.design, self.context)

    def test_nonpositive_weight_fails_closed(self):
        weights = list(self.design.weights)
        weights[0] = replace(weights[0], analysis_weight=0.0)
        with self.assertRaisesRegex(EstimationError, "positive"):
            estimate_poverty(
                self.measurement,
                self.domains,
                replace(self.design, weights=tuple(weights)),
                self.context,
            )


if __name__ == "__main__":
    unittest.main()
