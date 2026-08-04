import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.aggregation import AggregateContext, ClassifiedHousehold, ClassifiedPerson, aggregate_classified_tables
from poverty_pipeline.packaging import PackagingError, verify_release_bundle, write_release_bundle


class PackagingTests(unittest.TestCase):
    def test_bundle_is_complete_deterministic_and_immutable(self):
        rows = aggregate_classified_tables([ClassifiedPerson("p", "h")], [ClassifiedHousehold("h", "001", True, False, 2)], AggregateContext("r1", "2025-Q1"))
        kwargs = dict(input_manifests=[{"release": "input", "sha256": "a" * 64}], policies={"weight": "approved"}, software={"commit": "b" * 40}, qa={"reconciled": True}, limitations=["Research estimate; not official."])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = write_release_bundle(root / "one", rows, **kwargs)
            second = write_release_bundle(root / "two", rows, **kwargs)
            self.assertEqual(sorted(p.name for p in first.iterdir()), ["checksums.sha256", "estimates.csv", "limitations.md", "manifest.json", "qa.json"])
            for name in (p.name for p in first.iterdir()):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            verify_release_bundle(first)
            with self.assertRaisesRegex(PackagingError, "already exists"):
                write_release_bundle(first, rows, **kwargs)


if __name__ == "__main__":
    unittest.main()
