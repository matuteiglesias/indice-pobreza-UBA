import json
import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.adapters import adapt_census, adapt_income, to_linear_ars
from poverty_pipeline.contracts import ContractError
from tests.helpers import copy_release, rehash, rows, write_rows

ROOT = Path(__file__).parents[1]
PERSONS = adapt_census(ROOT / "fixtures/releases/census-sample-fixture-v1")[0]


class IncomeAdapterTests(unittest.TestCase):
    def test_three_distinct_transforms_exactly_once(self):
        fixtures = [("person-income-fixture-v1", "linear_ars", 1000, 0),
                    ("person-income-fixture-log10-v1", "log10_ars", 1000, 3),
                    ("person-income-fixture-log10-plus1-v1", "log10_ars_plus_1", 999, 3)]
        for fixture, source, expected, count in fixtures:
            with self.subTest(source=source):
                output, qa = adapt_income(ROOT / "fixtures/releases" / fixture, PERSONS, selected_period="2024-Q4", sample_id_namespace="cpv2010:test/v1")
                self.assertAlmostEqual(output[0]["prediction_value"], expected)
                self.assertEqual(qa["conversion_count"], count)
                self.assertEqual(qa["source_prediction_transform"], source)
                self.assertFalse(qa["scientific_execution_performed"])
        self.assertEqual(to_linear_ars(3, "log10_ars"), 1000)
        self.assertEqual(to_linear_ars(3, "log10_ars_plus_1"), 999)

    def mutate(self, operation, *, manifest_operation=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        release = copy_release(ROOT / "fixtures/releases/person-income-fixture-v1", Path(tmp.name) / "release")
        fields, values = rows(release / "person_income.csv"); operation(values)
        write_rows(release / "person_income.csv", fields, values); rehash(release, "person_income.csv")
        if manifest_operation:
            path=release/"manifest.json"; manifest=json.loads(path.read_text()); manifest_operation(manifest); path.write_text(json.dumps(manifest))
        return release

    def test_strict_duplicate_missing_and_extra_ids(self):
        cases=[(lambda v:v.append(dict(v[0])),"duplicate"),(lambda v:v.pop(),"missing"),
               (lambda v:v.append({**v[0],"sample_person_id":"extra"}),"extra")]
        for operation,message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ContractError,message): adapt_income(self.mutate(operation),PERSONS,selected_period="2024-Q4",sample_id_namespace="cpv2010:test/v1")

    def test_period_namespace_transform_and_double_transform_fail(self):
        with self.assertRaisesRegex(ContractError,"period"):
            adapt_income(self.mutate(lambda v:v[0].update(period="2025-Q1")),PERSONS,selected_period="2024-Q4",sample_id_namespace="cpv2010:test/v1")
        with self.assertRaisesRegex(ContractError,"namespace"):
            adapt_income(ROOT/"fixtures/releases/person-income-fixture-v1",PERSONS,selected_period="2024-Q4",sample_id_namespace="other")
        for value in ("unknown", "log10_ars"):
            with self.assertRaisesRegex(ContractError,"transform"):
                adapt_income(self.mutate(lambda v,value=value:v[0].update(prediction_transform=value)),PERSONS,selected_period="2024-Q4",sample_id_namespace="cpv2010:test/v1")

    def test_negative_nonfinite_and_unknown_manifest_transform(self):
        for value in ("-1", "nan", "inf"):
            with self.assertRaisesRegex(ContractError,"finite and nonnegative"):
                adapt_income(self.mutate(lambda v,value=value:v[0].update(prediction_value=value)),PERSONS,selected_period="2024-Q4",sample_id_namespace="cpv2010:test/v1")
        release=self.mutate(lambda v:None,manifest_operation=lambda m:m["compatibility"].update(prediction_transform="mystery"))
        with self.assertRaisesRegex(ContractError,"unknown"):
            adapt_income(release,PERSONS,selected_period="2024-Q4",sample_id_namespace="cpv2010:test/v1")
        with self.assertRaisesRegex(ContractError, "finite and nonnegative"):
            to_linear_ars(1000, "log10_ars")
        with self.assertRaisesRegex(ContractError, "multiplied"):
            adapt_income(ROOT/"fixtures/releases/person-income-fixture-v1", PERSONS + [PERSONS[0]], selected_period="2024-Q4", sample_id_namespace="cpv2010:test/v1")


if __name__ == "__main__": unittest.main()
