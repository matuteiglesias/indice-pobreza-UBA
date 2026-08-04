import math
import unittest
from dataclasses import replace

from poverty_pipeline.aggregation import AggregateContext, AggregationError, ClassifiedHousehold, ClassifiedPerson, aggregate_classified_tables, reconcile_national_to_departments


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.households = [ClassifiedHousehold("h1", "001", True, False, 2.0), ClassifiedHousehold("h2", "001", False, False, 1.0), ClassifiedHousehold("h3", "002", True, True, 3.0)]
        self.persons = [ClassifiedPerson("p1", "h1"), ClassifiedPerson("p2", "h1"), ClassifiedPerson("p3", "h2"), ClassifiedPerson("p4", "h3")]
        self.context = AggregateContext("release-1", "2025-Q1")

    def test_weighted_universes_and_reconciliation(self):
        rows = aggregate_classified_tables(self.persons, self.households, self.context)
        national = {(r.universe, r.observable): r for r in rows if r.geography_level == "national"}
        self.assertEqual((national["households", "poverty"].numerator, national["households", "poverty"].denominator), (5, 6))
        self.assertEqual((national["persons", "poverty"].numerator, national["persons", "poverty"].denominator), (7, 8))
        reconcile_national_to_departments(rows)

    def test_bad_weights_or_reconciliation_fail(self):
        with self.assertRaisesRegex(AggregationError, "finite and positive"):
            aggregate_classified_tables(self.persons, [replace(self.households[0], sample_weight=math.inf)] + self.households[1:], self.context)
        rows = list(aggregate_classified_tables(self.persons, self.households, self.context))
        index = next(i for i, row in enumerate(rows) if row.geography_level == "national")
        rows[index] = replace(rows[index], numerator=rows[index].numerator + .25, value=(rows[index].numerator + .25) / rows[index].denominator)
        with self.assertRaisesRegex(AggregationError, "does not reconcile"):
            reconcile_national_to_departments(rows)


if __name__ == "__main__":
    unittest.main()
