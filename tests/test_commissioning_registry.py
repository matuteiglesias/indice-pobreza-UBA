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

H64_A = "a" * 64
H64_B = "b" * 64
H64_C = "c" * 64
H40 = "d" * 40


def load():
    return REGISTRY.load_registry(ROOT / "science" / "commissioning" / "registry.json")


def identity(name: str, sha256: str = H64_A) -> dict[str, str]:
    return {"id": name, "sha256": sha256, "period": "2024-Q3"}


def closed_question(
    data: dict,
    sid: str,
    *,
    status: str,
    artifact_sha256: str,
) -> dict:
    surface = {item["id"]: item for item in data["surfaces"]}[sid]
    return {
        "period": "2024-Q3",
        "status": status,
        "producer": {
            "repository": surface["authority"]["repository"],
            "git_commit": H40,
        },
        "artifact": identity(f"{sid}-artifact", artifact_sha256),
        "parents": {},
        "evidence": [identity(f"{sid}-evidence")],
        "acceptance": {"status": "accepted", "checks": ["synthetic"]},
        "closure_reason": "synthetic accepted closure",
        "reopen_triggers": [surface["rerun_trigger"]],
    }


def valid_closure(data: dict) -> dict:
    closure = REGISTRY.build_closure_skeleton(
        data, "2024-Q3-commissioning-closure-v1"
    )
    questions = closure["questions"]
    questions["D-1"] = closed_question(
        data, "D-1", status="diagnostic_only", artifact_sha256=H64_A
    )
    questions["L2"] = closed_question(
        data, "L2", status="closed_pass", artifact_sha256=H64_B
    )
    questions["L3"] = closed_question(
        data, "L3", status="closed_pass", artifact_sha256=H64_C
    )
    questions["L4"] = closed_question(
        data, "L4", status="closed_negative", artifact_sha256="e" * 64
    )

    questions["D-1"]["parents"] = {}
    questions["L2"]["parents"] = {
        "L1": identity("L1-artifact"),
        "D-1": copy.deepcopy(questions["D-1"]["artifact"])
        | {"period": "2024-Q3"},
    }
    questions["L3"]["parents"] = {
        "L1": identity("L1-artifact"),
        "L2": copy.deepcopy(questions["L2"]["artifact"])
        | {"period": "2024-Q3"},
    }
    questions["L4"]["parents"] = {
        "L2": copy.deepcopy(questions["L2"]["artifact"])
        | {"period": "2024-Q3"},
        "L3": copy.deepcopy(questions["L3"]["artifact"])
        | {"period": "2024-Q3"},
        "T-B": identity("T-B-artifact"),
        "T-C": identity("T-C-artifact"),
    }

    questions["L2"]["feature_contract"] = {
        "id": "labor-bridge-feature-contract",
        "sha256": H64_A,
        "features": ["IX_TOT", "P03"],
    }
    questions["L3"]["calibration"] = {
        "domain_count": 32,
        "targets": identity("labor-targets"),
        "qa": identity("calibration-qa"),
        "gate_status": "PASS",
    }
    common = {
        "row_universe_sha256": "1" * 64,
        "folds_sha256": "2" * 64,
        "welfare_target_id": "welfare-target-v1",
        "scoring_contract_id": "scoring-v1",
        "model_family_id": "model-v1",
        "non_labor_feature_contract_sha256": "3" * 64,
    }
    questions["L4"]["comparison"] = {
        "arms": [
            {"name": name, **common}
            for name in [
                "no_labor",
                "true_labor_oracle",
                "transportable_labor_probabilities",
            ]
        ],
        "adjudication": {
            "oracle_labor_useful": "yes",
            "transportable_bridge_improves": "no",
        },
    }
    return closure


class CommissioningRegistryTest(unittest.TestCase):
    def test_registry_is_valid_and_small(self) -> None:
        data = load()
        result = REGISTRY.validate_registry(data)
        self.assertEqual(result["active_surfaces"], 9)
        self.assertEqual(result["historical_surfaces"], 3)
        self.assertEqual(result["closure_programs"], 1)
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


    def test_valid_synthetic_closure_passes(self) -> None:
        data = load()
        result = REGISTRY.validate_closure(valid_closure(data), data)
        self.assertTrue(result["all_terminal"])
        self.assertEqual(result["statuses"]["L4"], "closed_negative")

    def test_stale_l2_to_l3_parent_fails_closed(self) -> None:
        data = load()
        closure = valid_closure(data)
        closure["questions"]["L3"]["parents"]["L2"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(
            REGISTRY.RegistryError, "does not match closure artifact"
        ):
            REGISTRY.validate_closure(closure, data)

    def test_h06_in_corrected_l2_contract_fails_closed(self) -> None:
        data = load()
        closure = valid_closure(data)
        closure["questions"]["L2"]["feature_contract"]["features"].append("H06")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "forbidden features"):
            REGISTRY.validate_closure(closure, data)

    def test_l4_mismatched_folds_fail_closed(self) -> None:
        data = load()
        closure = valid_closure(data)
        closure["questions"]["L4"]["comparison"]["arms"][1]["folds_sha256"] = (
            "9" * 64
        )
        with self.assertRaisesRegex(
            REGISTRY.RegistryError,
            "differ on governed identity field folds_sha256",
        ):
            REGISTRY.validate_closure(closure, data)

    def test_terminal_closure_without_evidence_fails_closed(self) -> None:
        data = load()
        closure = valid_closure(data)
        closure["questions"]["L3"]["evidence"] = []
        with self.assertRaisesRegex(
            REGISTRY.RegistryError, "evidence must be a nonempty list"
        ):
            REGISTRY.validate_closure(closure, data)

    def test_wrong_quarter_parent_fails_closed(self) -> None:
        data = load()
        closure = valid_closure(data)
        closure["questions"]["L2"]["parents"]["D-1"]["period"] = "2024-Q2"
        with self.assertRaisesRegex(REGISTRY.RegistryError, "period mismatch"):
            REGISTRY.validate_closure(closure, data)


if __name__ == "__main__":
    unittest.main()
