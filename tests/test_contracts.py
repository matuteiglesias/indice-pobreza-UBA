import copy
import json
import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.contracts import ContractError, validate_lock, validate_release
from tests.helpers import copy_release

ROOT = Path(__file__).parents[1]


class ContractTests(unittest.TestCase):
    def test_content_locked_release_pair(self):
        lock = validate_lock(ROOT / "fixtures/slice-locks/contracts-only.yaml")
        self.assertFalse(lock["scientific_execution_authorized"])
        self.assertEqual(set(lock["_validated_releases"]), {"census", "income"})

    def test_tampered_file_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = copy_release(ROOT / "fixtures/releases/census-sample-fixture-v1", Path(tmp) / "release")
            (release / "persons.csv").write_text("tampered\n")
            with self.assertRaisesRegex(ContractError, "checksum mismatch"):
                validate_release(release, expected_artifact_type="research.census-sample/v1")

    def test_unsafe_path_and_artifact_substitution_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = copy_release(ROOT / "fixtures/releases/census-sample-fixture-v1", Path(tmp) / "release")
            manifest_path = release / "manifest.json"
            manifest = json.loads(manifest_path.read_text()); manifest["files"][0]["path"] = "../escape.csv"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ContractError, "unsafe"):
                validate_release(release, expected_artifact_type="research.census-sample/v1")
        with self.assertRaisesRegex(ContractError, "substitution"):
            validate_release(ROOT / "fixtures/releases/person-income-fixture-v1", expected_artifact_type="research.census-sample/v1")

    def test_pending_and_namespace_mismatch_lock_rejected(self):
        original = json.loads((ROOT / "fixtures/slice-locks/contracts-only.yaml").read_text())
        for mutate, message in ((lambda x: x.update(slice_id="PENDING_ID"), "placeholder"),
                                (lambda x: x["income"].update(sample_id_namespace="other"), "namespaces")):
            lock = copy.deepcopy(original); mutate(lock)
            with tempfile.NamedTemporaryFile("w", suffix=".yaml", dir=ROOT / "fixtures/slice-locks", delete=False) as stream:
                json.dump(lock, stream); path = Path(stream.name)
            try:
                with self.assertRaisesRegex(ContractError, message): validate_lock(path)
            finally: path.unlink()


if __name__ == "__main__": unittest.main()

