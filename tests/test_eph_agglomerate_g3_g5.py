from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from poverty_pipeline.contracts_v2 import prepare_measurement_inputs
from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    HouseholdDomain,
    HouseholdWeight,
    estimate_poverty,
)
from poverty_pipeline.release_v2 import ParentReleaseRef, write_estimate_release
from poverty_pipeline.science import load_poverty_method, measure_poverty
from tests.test_contracts_v2 import fixture_inputs


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "observed_agglomerate",
    ROOT / "scripts" / "build_observed_agglomerate_release.py",
)
OBS = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(OBS)


class EphAgglomerateG3G5Tests(unittest.TestCase):
    def _measurement(self):
        method = load_poverty_method(
            "configs/poverty_methods/indec-line-poverty-2016-v1.json"
        )
        frame, welfare, lines, binding = fixture_inputs()
        prepared = prepare_measurement_inputs(
            frame, welfare, lines, binding, method, estimation_period="2024-Q1"
        )
        measurement = measure_poverty(
            prepared.persons,
            prepared.household_welfare,
            prepared.household_lines,
            method,
        )
        design = EstimationDesign(
            "fixture",
            frame.weight_semantics,
            tuple(
                HouseholdWeight(h.household_id, h.analysis_weight)
                for h in frame.households
            ),
        )
        return method, frame, measurement, design

    def test_non_national_aggregate_is_explicit_and_reconciles(self):
        _, frame, measurement, design = self._measurement()
        domains = tuple(
            HouseholdDomain(
                h.household_id,
                "eph_agglomerate",
                "32" if h.household_id != "h3" else "33",
            )
            for h in frame.households
        )
        result = estimate_poverty(
            measurement,
            domains,
            design,
            EstimationContext(
                "aglo-test",
                "2024-Q1",
                "EPH",
                aggregate_geography_level="eph_coverage",
                aggregate_geography_id="EPH_TOTAL",
            ),
        )
        levels = {row.geography_level for row in result.estimates}
        self.assertEqual(levels, {"eph_agglomerate", "eph_coverage"})
        self.assertFalse(any(row.geography_id == "ARG" for row in result.estimates))
        aggregates = [
            row for row in result.estimates
            if row.geography_level == "eph_coverage"
        ]
        self.assertEqual(len(aggregates), 12)
        self.assertEqual({row.geography_id for row in aggregates}, {"EPH_TOTAL"})

    def test_legacy_default_stays_national_arg_without_manifest_delta(self):
        method, frame, measurement, design = self._measurement()
        domains = tuple(
            HouseholdDomain(h.household_id, "department_2010", h.department_2010_id)
            for h in frame.households
        )
        result = estimate_poverty(
            measurement,
            domains,
            design,
            EstimationContext("legacy-test", "2024-Q1", frame.frame_vintage),
        )
        self.assertEqual(
            {
                (row.geography_level, row.geography_id)
                for row in result.estimates
                if row.geography_level == "national"
            },
            {("national", "ARG")},
        )
        parents = (
            ParentReleaseRef("population_frame", "frame", "1" * 64),
            ParentReleaseRef("poverty_method", method.release_id, "2" * 64),
        )
        with TemporaryDirectory() as tmp:
            root = write_estimate_release(
                Path(tmp) / "release",
                result,
                parents=parents,
                method_release_id=method.release_id,
            )
            manifest = json.loads((root / "release_manifest.json").read_text())
            self.assertNotIn("aggregate_geography", manifest)

    def test_release_contract_marks_eph_total_non_spatial(self):
        method, frame, measurement, design = self._measurement()
        domains = tuple(
            HouseholdDomain(
                h.household_id,
                "eph_agglomerate",
                "32" if h.household_id != "h3" else "33",
            )
            for h in frame.households
        )
        result = estimate_poverty(
            measurement,
            domains,
            design,
            EstimationContext(
                "aglo-release-test",
                "2024-Q1",
                "EPH",
                aggregate_geography_level="eph_coverage",
                aggregate_geography_id="EPH_TOTAL",
            ),
        )
        parents = (
            ParentReleaseRef("population_frame", "frame", "1" * 64),
            ParentReleaseRef("poverty_method", method.release_id, "2" * 64),
        )
        with TemporaryDirectory() as tmp:
            root = write_estimate_release(
                Path(tmp) / "release",
                result,
                parents=parents,
                method_release_id=method.release_id,
            )
            manifest = json.loads((root / "release_manifest.json").read_text())
            join = json.loads((root / "geography_join_contract.json").read_text())
            self.assertEqual(
                manifest["aggregate_geography"],
                {"level": "eph_coverage", "id": "EPH_TOTAL"},
            )
            self.assertEqual(join["joinable_geography_levels"], ["eph_agglomerate"])
            self.assertEqual(join["non_spatial_levels"], ["eph_coverage"])

    def test_observed_microscope_aggregation_uses_existing_contributions(self):
        ids = [
            "02","03","04","05","06","07","08","09","10","12","13","14","15",
            "17","18","19","20","22","23","25","26","27","29","30","31","32",
            "33","34","36","38","91","93",
        ]
        rows = []
        for index, aglo in enumerate(ids):
            poor = 1.0 if index % 2 == 0 else 0.0
            indigent = 1.0 if index % 4 == 0 else 0.0
            rows.append(
                {
                    "period": "2024-Q3",
                    "household_id": f"h{aglo}",
                    "AGLOMERADO": int(aglo),
                    "member_count_records": 2,
                    "PONDIH": 10.0 + index,
                    "indigence_fgt0": indigent,
                    "indigence_fgt1": indigent * 0.5,
                    "indigence_fgt2": indigent * 0.25,
                    "poverty_fgt0": poor,
                    "poverty_fgt1": poor * 0.4,
                    "poverty_fgt2": poor * 0.16,
                }
            )
        estimation, diagnostics = OBS.build_estimation(
            pd.DataFrame(rows),
            period="2024-Q3",
            release_id="observed-test",
            expected_ids=set(ids),
            frame_vintage="EPH",
        )
        self.assertEqual(len(estimation.estimates), 32 * 12 + 12)
        self.assertEqual(diagnostics["poverty_recomputed"], False)
        self.assertEqual(
            {row.geography_id for row in estimation.estimates if row.geography_level == "eph_coverage"},
            {"EPH_TOTAL"},
        )


if __name__ == "__main__":
    unittest.main()
