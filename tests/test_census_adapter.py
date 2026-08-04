import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.adapters.census import adapt_census
from poverty_pipeline.contracts import ContractError
from tests.helpers import copy_release, rehash, rows, write_rows

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "fixtures/releases/census-sample-fixture-v1"


class CensusAdapterTests(unittest.TestCase):
    def test_valid_relations_leading_zeroes_and_order(self):
        persons, households, qa = adapt_census(SOURCE)
        self.assertEqual(persons[0]["radio_2010_id"], "020010101")
        self.assertEqual(households[0]["department_2010_id"], "02001")
        self.assertEqual(qa["foreign_key_coverage"], 1.0)
        self.assertFalse(qa["scientific_execution_performed"])

    def mutate(self, filename, operation):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        release = copy_release(SOURCE, Path(tmp.name) / "release")
        fields, values = rows(release / filename); operation(values)
        write_rows(release / filename, fields, values); rehash(release, filename)
        return release

    def test_duplicate_person_and_household_or_conflicting_geography(self):
        for filename, operation, message in [
            ("persons.csv", lambda v: v.append(dict(v[0])), "duplicate sample_person"),
            ("households.csv", lambda v: v.append({**v[0], "region_id": "conflict"}), "duplicate sample_household")]:
            with self.subTest(filename=filename):
                with self.assertRaisesRegex(ContractError, message): adapt_census(self.mutate(filename, operation))

    def test_orphan_and_invalid_weights(self):
        cases = [(lambda v: v[0].update(sample_household_id="missing"), "orphan")]
        cases += [(lambda v, value=value: v[0].update(sample_weight=value), "finite and positive") for value in ("", "-1", "nan", "inf")]
        for operation, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ContractError, message): adapt_census(self.mutate("persons.csv", operation))

    def test_missing_geography_rejected(self):
        with self.assertRaisesRegex(ContractError, "department and region"):
            adapt_census(self.mutate("households.csv", lambda v: v[0].update(region_id="")))


if __name__ == "__main__": unittest.main()

