import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.release_v2 import verify_estimate_release

_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_predictive_province_release.py"
_SPEC = importlib.util.spec_from_file_location("predictive_province_release", _SCRIPT)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)
build_release = _MODULE.build_release


class PredictiveProvinceReleaseTest(unittest.TestCase):
    def test_golden_fixture_emits_complete_research_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.json"
            frame.write_text(json.dumps({
                "release_id": "frame-fixture-2024",
                "households": [
                    {"household_id": "h1", "province_2010_id": "02", "region_id": "gran_buenos_aires", "analysis_weight": 1.0},
                    {"household_id": "h2", "province_2010_id": "02", "region_id": "gran_buenos_aires", "analysis_weight": 1.0},
                    {"household_id": "h3", "province_2010_id": "06", "region_id": "pampeana", "analysis_weight": 1.0},
                ],
                "persons": [
                    {"person_id": "p1", "household_id": "h1", "sex": "male", "age": 35},
                    {"person_id": "p2", "household_id": "h1", "sex": "female", "age": 34},
                    {"person_id": "p3", "household_id": "h2", "sex": "female", "age": 76},
                    {"person_id": "p4", "household_id": "h3", "sex": "male", "age": 10},
                ],
            }), encoding="utf-8")
            welfare = root / "welfare.json"
            welfare.write_text(json.dumps({
                "manifest": {"release_id": "welfare-fixture-2024"},
                "households": [
                    {"household_id": "h1", "point_welfare": 260.0, "estimation_status": "estimated"},
                    {"household_id": "h2", "point_welfare": 75.0, "estimation_status": "estimated"},
                    {"household_id": "h3", "point_welfare": 100.0, "estimation_status": "estimated"},
                ],
                "residuals": [{"residual": -10.0}, {"residual": 0.0}, {"residual": 10.0}],
            }), encoding="utf-8")
            baskets = root / "baskets.json"
            regions = ("cuyo", "gran_buenos_aires", "noreste", "noroeste", "pampeana", "patagonia")
            baskets.write_text(json.dumps([
                {"period": "2024-Q3", "region_id": region, "measure": measure, "value_2016_01": value}
                for region in regions
                for measure, value in (("CBA", 100.0), ("CBT", 180.0))
            ]), encoding="utf-8")
            output = root / "release"
            built = build_release(
                welfare_path=welfare, frame_path=frame, baskets_path=baskets,
                method_path=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
                output=output, expected_provinces=2, expected_households=3, expected_persons=4,
            )
            verify_estimate_release(built)
            manifest = json.loads((built / "release_manifest.json").read_text())
            capabilities = json.loads((built / "capabilities.json").read_text())
            rows = (built / "poverty_estimates.csv").read_text().splitlines()
            self.assertEqual(manifest["scientific_status"], "research_estimate")
            self.assertEqual(manifest["uncertainty_status"], "not_supplied")
            self.assertEqual(len(rows) - 1, 2 * 12 + 12)
            self.assertEqual(capabilities["dimensions"]["universes"], ["households", "persons"])
            self.assertEqual(capabilities["dimensions"]["concepts"], ["indigence", "poverty"])
            self.assertEqual(capabilities["dimensions"]["estimands"], ["fgt0", "fgt1", "fgt2"])


if __name__ == "__main__":
    unittest.main()
