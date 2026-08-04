import json
import math
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from poverty_pipeline.science.household_poverty import (
    AdultEquivalenceCell, ComparisonPolicy, GapSignPolicy, Household, LinearIncome,
    NormalizedPerson, PovertyInputError, PovertyPolicies, RegionalPeriodBasket,
    ScientificDependencyContract, WeightUsePolicy,
    calculate_household_poverty,
)

FIXTURE = Path(__file__).parent / "fixtures/household_poverty_golden.json"


def inputs():
    raw = json.loads(FIXTURE.read_text())
    return raw, [NormalizedPerson(**x) for x in raw["persons"]], [Household(**x) for x in raw["households"]], [LinearIncome(**x) for x in raw["incomes"]], [AdultEquivalenceCell(**x) for x in raw["equivalence_cells"]], [RegionalPeriodBasket(**x) for x in raw["baskets"]]


def governance():
    policies = PovertyPolicies(
        ComparisonPolicy.BELOW, ComparisonPolicy.BELOW,
        GapSignPolicy.INCOME_MINUS_THRESHOLD, True,
        WeightUsePolicy.RETAIN_FOR_PUBLICATION, "resident_households",
    )
    contract = ScientificDependencyContract(
        "sample-v1", "2025-Q1", "resident_households", "census-release@abc",
        "projection-method-v1", "prediction-release@def", "linear_ars", "ARS",
        "2025-Q1", "projected", "ae-method-v1", "ae-release@ghi", ("F", "M"),
        0, 120, "basket-release@jkl", "ARS", "2025-Q1",
        "currency_per_adult_equivalent",
    )
    return policies, contract


class HouseholdPovertyGoldenTests(unittest.TestCase):
    def test_hand_calculated_strict_golden_fixture(self):
        raw, persons, households, incomes, cells, baskets = inputs()
        policies, contract = governance()
        actual = {x.household_id: asdict(x) for x in calculate_household_poverty(persons, households, incomes, cells, baskets, policies, contract)}
        for household_id, expected in raw["expected"].items():
            for field, value in expected.items():
                self.assertEqual(actual[household_id][field], value)

    def test_equality_and_gap_sign_are_explicit_policies(self):
        _, persons, households, incomes, cells, baskets = inputs()
        base, contract = governance()
        policies = replace(base, poverty_comparison=ComparisonPolicy.AT_OR_BELOW, indigence_comparison=ComparisonPolicy.AT_OR_BELOW, gap_sign=GapSignPolicy.THRESHOLD_MINUS_INCOME)
        actual = {x.household_id: x for x in calculate_household_poverty(persons, households, incomes, cells, baskets, policies, contract)}
        self.assertTrue(actual["equal-cbt"].poverty)
        self.assertTrue(actual["equal-cba"].indigence)
        self.assertEqual(actual["north"].poverty_gap, 300.0)

    def test_duplicate_missing_and_invalid_values_are_rejected(self):
        _, persons, households, incomes, cells, baskets = inputs()
        policy, contract = governance()
        cases = [
            (persons + [persons[0]], households, incomes, cells, baskets, "duplicate person"),
            (persons, households, incomes[:-1], cells, baskets, "income mapping"),
            (persons, households, incomes, cells[:-1], baskets, "approved age domain"),
            (persons, households, [replace(incomes[0], amount=math.inf)] + incomes[1:], cells, baskets, "linear income"),
            (persons, households, [replace(incomes[0], amount=-1)] + incomes[1:], cells, baskets, "linear income"),
            (persons, households, incomes, cells, [replace(baskets[0], cba=201)] + baskets[1:], "CBA must"),
        ]
        for args in cases:
            with self.subTest(message=args[-1]), self.assertRaisesRegex(PovertyInputError, args[-1]):
                calculate_household_poverty(*args[:-1], policy, contract)

    def test_cartesian_region_period_basket_coverage_is_required(self):
        _, persons, households, incomes, cells, baskets = inputs()
        households[1] = replace(households[1], period="2025-Q2")
        baskets.append(RegionalPeriodBasket("S", "2025-Q2", 160, 320))
        policy, contract = governance()
        contract = replace(contract, period="2025-Q2")
        with self.assertRaisesRegex(PovertyInputError, "incomplete region-period"):
            # Make all household rows agree with the governed period first.
            households = [replace(x, period="2025-Q2") for x in households]
            calculate_household_poverty(persons, households, incomes, cells, baskets, policy, contract)

    def test_dependency_semantics_and_positive_weights_are_enforced(self):
        _, persons, households, incomes, cells, baskets = inputs()
        policy, contract = governance()
        bad_contracts = [
            (replace(contract, income_transform="log10_ars_plus_1"), "linear income"),
            (replace(contract, basket_currency="USD"), "currency and price"),
            (replace(contract, basket_unit="per_household"), "per adult equivalent"),
        ]
        for bad, message in bad_contracts:
            with self.subTest(message=message), self.assertRaisesRegex(PovertyInputError, message):
                calculate_household_poverty(persons, households, incomes, cells, baskets, policy, bad)
        with self.assertRaisesRegex(PovertyInputError, "positive"):
            calculate_household_poverty(persons, [replace(households[0], sample_weight=0)] + households[1:], incomes, cells, baskets, policy, contract)


if __name__ == "__main__":
    unittest.main()
