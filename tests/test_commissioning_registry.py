from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "commissioning_registry",
    ROOT / "science" / "commissioning" / "registry.py",
)
REGISTRY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(REGISTRY)


def load():
    return REGISTRY.load_registry(ROOT / "science" / "commissioning" / "registry.json")


class CommissioningRegistryTest(unittest.TestCase):
    def test_registry_is_valid_and_small(self) -> None:
        data = load()
        result = REGISTRY.validate_registry(data)
        self.assertEqual(result["active_surfaces"], 9)
        self.assertEqual(result["historical_surfaces"], 3)
        self.assertIs(data["invariants"]["no_generic_raking_or_ipf"], True)
        self.assertIs(
            data["invariants"]["census_design_inverse_probability_is_analysis_weight"],
            False,
        )

    def test_registry_has_single_authority_for_each_active_question(self) -> None:
        data = load()
        ids = [surface["id"] for surface in data["surfaces"]]
        self.assertEqual(
            ids, ["T-A", "T-B", "T-C", "L1", "L2", "L3", "L4", "D-1", "OBS"]
        )
        by_id = {surface["id"]: surface for surface in data["surfaces"]}
        self.assertEqual(by_id["T-A"]["stage"], "truth")
        self.assertEqual(by_id["T-B"]["stage"], "within_domain_model")
        self.assertEqual(by_id["T-C"]["stage"], "transport")
        self.assertEqual(by_id["L1"]["stage"], "truth")
        self.assertEqual(by_id["L3"]["stage"], "calibration")
        self.assertEqual(by_id["L4"]["stage"], "downstream_impact")
        self.assertTrue(
            by_id["D-1"]["promotion_role"].endswith(
                "never generates transport weights."
            )
        )

    def test_weight_and_calibration_semantics_do_not_collapse(self) -> None:
        data = load()
        by_id = {surface["id"]: surface for surface in data["surfaces"]}
        self.assertEqual(by_id["L1"]["weights"]["measurement"], "PONDERA")
        self.assertEqual(by_id["T-A"]["weights"]["measurement"], "PONDIH")
        self.assertEqual(
            by_id["T-B"]["calibration"]["kind"], "nested_outer_fold_residual_ecdf"
        )
        self.assertEqual(by_id["L3"]["calibration"]["kind"], "two_logit_offsets")
        self.assertEqual(by_id["D-1"]["calibration"]["kind"], "none")
        self.assertIn("design-IPW", by_id["L3"]["weights"]["transport"])

    def test_superseded_wedges_are_not_active_surfaces(self) -> None:
        data = load()
        active = {surface["id"] for surface in data["surfaces"]}
        historical = {item["id"]: item for item in data["superseded"]}
        self.assertNotIn("Q8-global-domain-classifier", active)
        self.assertEqual(
            historical["Q8-global-domain-classifier"]["replaced_by"], "D-1"
        )
        self.assertEqual(
            historical["legacy-ajustar-empleo"]["status"], "superseded"
        )

    def test_unknown_dependency_fails_closed(self) -> None:
        data = copy.deepcopy(load())
        data["surfaces"][0]["depends_on"] = ["DOES-NOT-EXIST"]
        with self.assertRaisesRegex(REGISTRY.RegistryError, "unknown dependencies"):
            REGISTRY.validate_registry(data)

    def test_dependency_cycle_fails_closed(self) -> None:
        data = copy.deepcopy(load())
        by_id = {surface["id"]: surface for surface in data["surfaces"]}
        by_id["T-A"]["depends_on"] = ["T-B"]
        with self.assertRaisesRegex(REGISTRY.RegistryError, "dependency cycle"):
            REGISTRY.validate_registry(data)


if __name__ == "__main__":
    unittest.main()
