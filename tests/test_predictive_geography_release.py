import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.release_v2 import verify_estimate_release


_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_predictive_geography_release.py"
_SPEC = importlib.util.spec_from_file_location("predictive_geography_release", _SCRIPT)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)

build_release = _MODULE.build_release
load_profiles = _MODULE.load_profiles


def _write_fixture(root: Path, *, field: str, ids: list[str], period: str = "2024-Q3"):
    households = []
    persons = []
    welfare_households = []
    for i, geography_id in enumerate(ids, start=1):
        household_id = f"h{i}"
        households.append(
            {
                "household_id": household_id,
                field: geography_id,
                "region_id": "pampeana",
                "analysis_weight": 1.0,
            }
        )
        persons.append(
            {"person_id": f"p{i}", "household_id": household_id, "sex": "female", "age": 30}
        )
        welfare_households.append(
            {
                "household_id": household_id,
                "point_welfare": 120.0 + i,
                "estimation_status": "estimated",
            }
        )
    frame = root / "frame.json"
    frame.write_text(
        json.dumps(
            {"release_id": "frame-fixture", "households": households, "persons": persons}
        ),
        encoding="utf-8",
    )
    welfare = root / "welfare.json"
    welfare.write_text(
        json.dumps(
            {
                "manifest": {"release_id": "welfare-fixture"},
                "households": welfare_households,
                "residuals": [{"residual": -10.0}, {"residual": 0.0}, {"residual": 10.0}],
            }
        ),
        encoding="utf-8",
    )
    regions = ("cuyo", "gran_buenos_aires", "noreste", "noroeste", "pampeana", "patagonia")
    baskets = root / "baskets.json"
    baskets.write_text(
        json.dumps(
            [
                {
                    "period": period,
                    "region_id": region,
                    "measure": measure,
                    "value_2016_01": value,
                }
                for region in regions
                for measure, value in (("CBA", 100.0), ("CBT", 180.0))
            ]
        ),
        encoding="utf-8",
    )
    return frame, welfare, baskets


class PredictiveGeographyReleaseTest(unittest.TestCase):
    def test_profiles_pin_governed_24_and_525_inventories(self):
        profiles = load_profiles()
        self.assertEqual(len(profiles["province_2010"]["expected_ids"]), 24)
        self.assertEqual(len(profiles["department_2010"]["expected_ids"]), 525)
        self.assertEqual(len(profiles["eph_agglomerate"]["expected_ids"]), 32)
        self.assertEqual(
            profiles["eph_agglomerate"]["aggregate_geography_id"],
            "EPH_TOTAL",
        )
        self.assertIn("02001", profiles["department_2010"]["expected_ids"])
        self.assertTrue(
            all(len(value) == 5 for value in profiles["department_2010"]["expected_ids"])
        )

    def test_generic_producer_emits_exact_profile_facts(self):
        cases = (
            ("province_2010", "province_2010_id", ["02", "06"]),
            ("department_2010", "department_2010_id", ["02001", "06028"]),
        )
        for level, field, ids in cases:
            with self.subTest(level=level), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                frame, welfare, baskets = _write_fixture(root, field=field, ids=ids)
                output = root / "release"
                built = build_release(
                    welfare_path=welfare,
                    frame_path=frame,
                    baskets_path=baskets,
                    method_path=Path(
                        "configs/poverty_methods/indec-line-poverty-2016-v1.json"
                    ),
                    output=output,
                    period="2024-Q3",
                    geography_level=level,
                    expected_geography_ids=set(ids),
                    expected_households=2,
                    expected_persons=2,
                )
                verify_estimate_release(built)
                rows = (
                    (built / "poverty_estimates.csv")
                    .read_text(encoding="utf-8")
                    .splitlines()
                )
                self.assertEqual(len(rows) - 1, len(ids) * 12 + 12)
                manifest = json.loads(
                    (built / "release_manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(manifest["estimation_period"], "2024-Q3")
                suffix = (
                    "-province-predictive-v1"
                    if level == "province_2010"
                    else "-department-predictive-v1"
                )
                self.assertTrue(manifest["release_id"].endswith(suffix))


    def test_agglomerate_profile_filters_outside_frame_and_uses_explicit_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame, welfare, baskets = _write_fixture(
                root,
                field="eph_agglomerate_id",
                ids=["32", "33", "91"],
            )
            frame_payload = json.loads(frame.read_text(encoding="utf-8"))
            frame_payload["households"][0]["mapped_to_eph_frame"] = True
            frame_payload["households"][1]["mapped_to_eph_frame"] = True
            frame_payload["households"][2]["mapped_to_eph_frame"] = False
            frame_payload["households"][2]["eph_agglomerate_id"] = None
            frame.write_text(json.dumps(frame_payload), encoding="utf-8")

            binding = root / "binding.json"
            binding.write_text(
                json.dumps(
                    {
                        "schema_version": "poverty-threshold-area-binding/eph-agglomerate-v1",
                        "release_id": "aglo-binding-test",
                        "geography_level": "eph_agglomerate",
                        "rows": [
                            {
                                "geography_level": "eph_agglomerate",
                                "geography_id": "32",
                                "poverty_region_id": "gran_buenos_aires",
                            },
                            {
                                "geography_level": "eph_agglomerate",
                                "geography_id": "33",
                                "poverty_region_id": "pampeana",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            output = root / "release"
            built = build_release(
                welfare_path=welfare,
                frame_path=frame,
                baskets_path=baskets,
                method_path=Path(
                    "configs/poverty_methods/indec-line-poverty-2016-v1.json"
                ),
                output=output,
                period="2024-Q3",
                geography_level="eph_agglomerate",
                expected_geography_ids={"32", "33"},
                threshold_area_binding_path=binding,
            )
            verify_estimate_release(built)
            rows = list(
                __import__("csv").DictReader(
                    (built / "poverty_estimates.csv").open(
                        newline="", encoding="utf-8"
                    )
                )
            )
            territorial = [row for row in rows if row["geography_level"] == "eph_agglomerate"]
            aggregate = [row for row in rows if row["geography_level"] == "eph_coverage"]
            self.assertEqual({row["geography_id"] for row in territorial}, {"32", "33"})
            self.assertEqual({row["geography_id"] for row in aggregate}, {"EPH_TOTAL"})
            self.assertEqual(len(territorial), 24)
            self.assertEqual(len(aggregate), 12)
            manifest = json.loads(
                (built / "release_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["aggregate_geography"],
                {"level": "eph_coverage", "id": "EPH_TOTAL"},
            )
            # Unit weights over the retained mapped subset: 2 households / 2 persons.
            household_poverty = next(
                row for row in aggregate
                if row["universe"] == "households"
                and row["concept"] == "poverty"
                and row["estimand"] == "fgt0"
            )
            person_poverty = next(
                row for row in aggregate
                if row["universe"] == "persons"
                and row["concept"] == "poverty"
                and row["estimand"] == "fgt0"
            )
            self.assertEqual(float(household_poverty["weighted_denominator"]), 2.0)
            self.assertEqual(float(person_poverty["weighted_denominator"]), 2.0)

    def test_department_id_must_already_be_zero_preserving_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame, welfare, baskets = _write_fixture(
                root, field="department_2010_id", ids=["02001"]
            )
            payload = json.loads(frame.read_text(encoding="utf-8"))
            payload["households"][0]["department_2010_id"] = 2001
            frame.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "numeric geography coercion is forbidden"
            ):
                build_release(
                    welfare_path=welfare,
                    frame_path=frame,
                    baskets_path=baskets,
                    method_path=Path(
                        "configs/poverty_methods/indec-line-poverty-2016-v1.json"
                    ),
                    output=root / "release",
                    period="2024-Q3",
                    geography_level="department_2010",
                    expected_geography_ids={"02001"},
                )

    def test_exact_inventory_rejects_missing_plus_extra_even_when_count_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame, welfare, baskets = _write_fixture(
                root, field="department_2010_id", ids=["02001", "06028"]
            )
            with self.assertRaisesRegex(ValueError, "do not equal governed inventory"):
                build_release(
                    welfare_path=welfare,
                    frame_path=frame,
                    baskets_path=baskets,
                    method_path=Path(
                        "configs/poverty_methods/indec-line-poverty-2016-v1.json"
                    ),
                    output=root / "release",
                    period="2024-Q3",
                    geography_level="department_2010",
                    expected_geography_ids={"02001", "06035"},
                )

    def test_basket_period_is_exact_not_q3_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame, welfare, baskets = _write_fixture(
                root, field="department_2010_id", ids=["02001"], period="2024-Q3"
            )
            with self.assertRaisesRegex(ValueError, "2024-Q2"):
                build_release(
                    welfare_path=welfare,
                    frame_path=frame,
                    baskets_path=baskets,
                    method_path=Path(
                        "configs/poverty_methods/indec-line-poverty-2016-v1.json"
                    ),
                    output=root / "release",
                    period="2024-Q2",
                    geography_level="department_2010",
                    expected_geography_ids={"02001"},
                )


if __name__ == "__main__":
    unittest.main()
