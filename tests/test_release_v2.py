import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from poverty_pipeline.contracts_v2 import prepare_measurement_inputs
from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    HouseholdDomain,
    HouseholdWeight,
    estimate_poverty,
)
from poverty_pipeline.release_v2 import (
    EstimateReleaseError,
    ParentReleaseRef,
    verify_estimate_release,
    write_estimate_release,
)
from poverty_pipeline.science import load_poverty_method, measure_poverty
from tests.test_contracts_v2 import fixture_inputs


class V2ReleaseTest(unittest.TestCase):
    def _estimation(self, geography_level="department_2010"):
        method = load_poverty_method("configs/poverty_methods/indec-line-poverty-2016-v1.json")
        frame, welfare, lines, binding = fixture_inputs()
        prepared = prepare_measurement_inputs(
            frame, welfare, lines, binding, method, estimation_period="2024-Q1"
        )
        measurement = measure_poverty(
            prepared.persons, prepared.household_welfare, prepared.household_lines, method
        )
        design = EstimationDesign(
            "fixture-design-v2",
            frame.weight_semantics,
            tuple(HouseholdWeight(h.household_id, h.analysis_weight) for h in frame.households),
        )
        if geography_level == "department_2010":
            domains = tuple(
                HouseholdDomain(h.household_id, geography_level, h.department_2010_id)
                for h in frame.households
            )
        elif geography_level == "province_2010":
            domains = tuple(
                HouseholdDomain(h.household_id, geography_level, h.province_2010_id)
                for h in frame.households
            )
        else:
            raise AssertionError(f"unsupported test geography: {geography_level}")
        estimation = estimate_poverty(
            measurement,
            domains,
            design,
            EstimationContext("poverty-estimate-fixture-v2", "2024-Q1", frame.frame_vintage),
        )
        parents = (
            ParentReleaseRef("population_frame", frame.release_id, "1" * 64),
            ParentReleaseRef("welfare", welfare.release_id, "2" * 64),
            ParentReleaseRef("poverty_lines", lines.release_id, "3" * 64),
            ParentReleaseRef("threshold_area_binding", binding.release_id, "4" * 64),
            ParentReleaseRef("poverty_method", method.release_id, "5" * 64),
        )
        return method, estimation, parents

    def test_release_is_geometry_free_and_self_describing(self):
        method, estimation, parents = self._estimation()
        with TemporaryDirectory() as tmp:
            root = write_estimate_release(
                Path(tmp) / "release",
                estimation,
                parents=parents,
                method_release_id=method.release_id,
            )
            verify_estimate_release(root)
            join = json.loads((root / "geography_join_contract.json").read_text())
            capabilities = json.loads((root / "capabilities.json").read_text())
            manifest = json.loads((root / "release_manifest.json").read_text())
            self.assertFalse(join["geometry_embedded"])
            self.assertEqual(join["geometry_owner"], "matuteiglesias/argentina-geography")
            self.assertEqual(join["join_key"], ["geography_level", "geography_id"])
            self.assertEqual(join["joinable_geography_levels"], ["department_2010"])
            self.assertEqual(capabilities["scientific_status"], "synthetic_fixture")
            self.assertEqual(capabilities["dimensions"]["geography_levels"], ["department_2010", "national"])
            self.assertIn("capabilities", manifest["output_roles"])
            with (root / "poverty_estimates.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertNotIn("geometry", rows[0])
            map_rows = [r for r in rows if r["universe"] == "persons"
                        and r["concept"] == "poverty" and r["estimand"] == "fgt0"
                        and r["geography_level"] == "department_2010"]
            self.assertEqual({r["geography_id"] for r in map_rows}, {"02001", "06014"})

    def test_province_release_requires_no_packager_special_case(self):
        method, estimation, parents = self._estimation("province_2010")
        with TemporaryDirectory() as tmp:
            root = write_estimate_release(
                Path(tmp) / "release",
                estimation,
                parents=parents,
                method_release_id=method.release_id,
            )
            join = json.loads((root / "geography_join_contract.json").read_text())
            capabilities = json.loads((root / "capabilities.json").read_text())
            self.assertEqual(join["joinable_geography_levels"], ["province_2010"])
            recommended = join["recommended_map_measure"]
            self.assertEqual(recommended["geography_level"], "province_2010")
            province_cells = [
                cell for cell in capabilities["availability"]
                if cell["geography_level"] == "province_2010"
                and cell["universe"] == "persons"
                and cell["concept"] == "poverty"
                and cell["estimand"] == "fgt0"
            ]
            self.assertEqual(len(province_cells), 1)
            self.assertEqual(province_cells[0]["geography_count"], 2)

    def test_release_is_deterministic(self):
        method, estimation, parents = self._estimation()
        with TemporaryDirectory() as tmp:
            left = write_estimate_release(Path(tmp) / "left", estimation,
                                          parents=parents, method_release_id=method.release_id)
            right = write_estimate_release(Path(tmp) / "right", estimation,
                                           parents=parents, method_release_id=method.release_id)
            for name in (
                "poverty_estimates.csv", "capabilities.json", "geography_join_contract.json",
                "release_manifest.json", "run_qa.json", "LIMITATIONS.md", "checksums.sha256",
            ):
                self.assertEqual((left / name).read_bytes(), (right / name).read_bytes())

    def test_tamper_is_detected(self):
        method, estimation, parents = self._estimation()
        with TemporaryDirectory() as tmp:
            root = write_estimate_release(Path(tmp) / "release", estimation,
                                          parents=parents, method_release_id=method.release_id)
            with (root / "poverty_estimates.csv").open("a", encoding="utf-8") as handle:
                handle.write("tamper\n")
            with self.assertRaisesRegex(EstimateReleaseError, "checksum mismatch"):
                verify_estimate_release(root)

    def test_method_parent_identity_is_not_optional(self):
        method, estimation, parents = self._estimation()
        wrong = tuple(
            ParentReleaseRef(parent.role, "wrong-method" if parent.role == "poverty_method" else parent.release_id,
                             parent.content_sha256)
            for parent in parents
        )
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(EstimateReleaseError, "poverty_method parent"):
                write_estimate_release(
                    Path(tmp) / "release",
                    estimation,
                    parents=wrong,
                    method_release_id=method.release_id,
                )


if __name__ == "__main__":
    unittest.main()
