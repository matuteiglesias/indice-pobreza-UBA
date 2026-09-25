import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


_BATCH_SCRIPT = Path(__file__).parents[1] / "scripts" / "run_predictive_geography_batch.py"
_BATCH_SPEC = importlib.util.spec_from_file_location("predictive_geography_batch", _BATCH_SCRIPT)
_BATCH_MODULE = importlib.util.module_from_spec(_BATCH_SPEC)
assert _BATCH_SPEC and _BATCH_SPEC.loader
_BATCH_SPEC.loader.exec_module(_BATCH_MODULE)

_RECONCILE_SCRIPT = Path(__file__).parents[1] / "scripts" / "reconcile_predictive_geographies.py"
_RECONCILE_SPEC = importlib.util.spec_from_file_location(
    "reconcile_predictive_geographies_test", _RECONCILE_SCRIPT
)
_RECONCILE_MODULE = importlib.util.module_from_spec(_RECONCILE_SPEC)
assert _RECONCILE_SPEC and _RECONCILE_SPEC.loader
_RECONCILE_SPEC.loader.exec_module(_RECONCILE_MODULE)

run_batch = _BATCH_MODULE.run_batch
validate_batch_spec = _BATCH_MODULE.validate_batch_spec
reconcile_releases = _RECONCILE_MODULE.reconcile_releases

PERIODS = [
    "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
    "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _batch_spec() -> dict:
    return {
        "schema_version": "predictive-poverty-batch/v1",
        "batch_id": "department-poverty-2024q1-2025q4",
        "geography_level": "department_2010",
        "frame_vintage": "2010",
        "periods": [
            {
                "period": period,
                "target_year": int(period[:4]),
                "census_sample_release_ref": f"census-sample:{period[:4]}",
                "frame_ref": f"population-frame:{period[:4]}",
                "semantic_plane_release_ref": f"semantic-plane:{period}",
                "predictive_welfare_release_ref": f"predictive-welfare:{period}",
                "basket_slice_ref": f"basket:{period}",
            }
            for period in PERIODS
        ],
    }


class PredictiveGeographyBatchTest(unittest.TestCase):
    def test_committed_batch_spec_is_exact_and_path_free(self):
        path = Path("configs/releases/predictive-poverty-2024q1-2025q4.json")
        spec = json.loads(path.read_text(encoding="utf-8"))
        validate_batch_spec(spec)
        self.assertEqual([row["period"] for row in spec["periods"]], PERIODS)
        self.assertEqual(
            {row["census_sample_release_ref"] for row in spec["periods"][:4]},
            {"census-sample:2024"},
        )
        self.assertEqual(
            {row["census_sample_release_ref"] for row in spec["periods"][4:]},
            {"census-sample:2025"},
        )
        self.assertNotIn('"/', path.read_text(encoding="utf-8"))

    def test_fixture_batch_executes_all_eight_periods_and_reconciles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = _write_json(root / "batch.json", _batch_spec())
            profile_path = _write_json(
                root / "profiles.json",
                {
                    "schema_version": "poverty-geography-profiles/v1",
                    "profiles": {
                        "province_2010": {
                            "field": "province_2010_id",
                            "id_regex": "^[0-9]{2}$",
                            "expected_ids": ["02", "06"],
                        },
                        "department_2010": {
                            "field": "department_2010_id",
                            "id_regex": "^[0-9]{5}$",
                            "expected_ids": ["02001", "06028"],
                        },
                    },
                },
            )
            frame_paths = {}
            for year in ("2024", "2025"):
                frame_paths[year] = _write_json(
                    root / f"frame-{year}.json",
                    {
                        "release_id": f"frame-{year}",
                        "households": [
                            {
                                "household_id": "h1",
                                "department_2010_id": "02001",
                                "province_2010_id": "02",
                                "region_id": "gran_buenos_aires",
                                "analysis_weight": 1.0,
                            },
                            {
                                "household_id": "h2",
                                "department_2010_id": "06028",
                                "province_2010_id": "06",
                                "region_id": "pampeana",
                                "analysis_weight": 1.0,
                            },
                        ],
                        "persons": [
                            {"person_id": "p1", "household_id": "h1", "sex": "female", "age": 30},
                            {"person_id": "p2", "household_id": "h2", "sex": "male", "age": 40},
                        ],
                    },
                )

            welfare = _write_json(
                root / "welfare.json",
                {
                    "manifest": {"release_id": "welfare-fixture"},
                    "households": [
                        {"household_id": "h1", "point_welfare": 80.0, "estimation_status": "estimated"},
                        {"household_id": "h2", "point_welfare": 220.0, "estimation_status": "estimated"},
                    ],
                    "residuals": [{"residual": -10.0}, {"residual": 0.0}, {"residual": 10.0}],
                },
            )
            regions = ("cuyo", "gran_buenos_aires", "noreste", "noroeste", "pampeana", "patagonia")
            baskets = _write_json(
                root / "baskets.json",
                [
                    {
                        "period": period,
                        "region_id": region,
                        "measure": measure,
                        "value_2016_01": value,
                    }
                    for period in PERIODS
                    for region in regions
                    for measure, value in (("CBA", 100.0), ("CBT", 180.0))
                ],
            )
            census_paths = {
                year: _write_json(root / f"census-{year}.json", {"release_id": f"census-{year}"})
                for year in ("2024", "2025")
            }
            semantic_paths = {
                period: _write_json(
                    root / f"semantic-{period}.json",
                    {"release_id": f"semantic-{period}"},
                )
                for period in PERIODS
            }

            refs = {}
            for year in ("2024", "2025"):
                refs[f"census-sample:{year}"] = {
                    "path": str(census_paths[year]),
                    "sha256": _sha(census_paths[year]),
                }
                refs[f"population-frame:{year}"] = {
                    "path": str(frame_paths[year]),
                    "sha256": _sha(frame_paths[year]),
                }
            for period in PERIODS:
                refs[f"semantic-plane:{period}"] = {
                    "path": str(semantic_paths[period]),
                    "sha256": _sha(semantic_paths[period]),
                }
                refs[f"predictive-welfare:{period}"] = {
                    "path": str(welfare),
                    "sha256": _sha(welfare),
                }
                refs[f"basket:{period}"] = {
                    "path": str(baskets),
                    "sha256": _sha(baskets),
                }
            resolution_path = _write_json(
                root / "resolved.json",
                {
                    "schema_version": "predictive-poverty-parent-resolution/v1",
                    "refs": refs,
                },
            )

            batch_path = run_batch(
                spec_path=spec_path,
                resolved_parents_path=resolution_path,
                output=root / "output",
                profile_path=profile_path,
            )
            manifest = json.loads(batch_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["periods"]), 8)
            self.assertEqual(manifest["all_period_qa"]["reconciliation_status"], "PASS")
            self.assertEqual(manifest["all_period_qa"]["geography_count_each"], 2)
            self.assertEqual(manifest["all_period_qa"]["department_fact_count"], 192)
            self.assertEqual(manifest["all_period_qa"]["national_fact_count"], 96)
            self.assertEqual(manifest["all_period_qa"]["fact_count"], 288)
            self.assertTrue((root / "output" / "parent_resolution_report.json").is_file())
            self.assertTrue((root / "output" / "reconciliation_report.json").is_file())
            self.assertTrue((root / "output" / "checksums.sha256").is_file())

    def test_reconciliation_detects_oracle_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            departments = root / "departments"
            provinces = root / "provinces"
            departments.mkdir()
            provinces.mkdir()
            header = (
                "release_id,estimation_period,frame_vintage,universe,geography_level,"
                "geography_id,concept,estimand,estimate,unit,weighted_numerator,"
                "weighted_denominator,coverage,design_id,weight_semantics,uncertainty_status\n"
            )
            department_row = (
                "d,2024-Q1,2010,households,department_2010,02001,poverty,fgt0,"
                "0.25,proportion,25,100,1,design,unit_analysis_weight,not_supplied\n"
            )
            province_row = (
                "p,2024-Q1,2010,households,province_2010,02,poverty,fgt0,"
                "0.26,proportion,26,100,1,design,unit_analysis_weight,not_supplied\n"
            )
            national_row = (
                "p,2024-Q1,2010,households,national,ARG,poverty,fgt0,"
                "0.25,proportion,25,100,1,design,unit_analysis_weight,not_supplied\n"
            )
            (departments / "poverty_estimates.csv").write_text(
                header + department_row, encoding="utf-8"
            )
            (provinces / "poverty_estimates.csv").write_text(
                header + province_row + national_row, encoding="utf-8"
            )
            report = reconcile_releases(departments, provinces)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["failure_count"], 1)
            self.assertEqual(
                report["failures"][0]["kind"], "department_to_province_mismatch"
            )


if __name__ == "__main__":
    unittest.main()
