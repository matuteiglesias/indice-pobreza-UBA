from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

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


def test_registry_is_valid_and_small() -> None:
    data = load()
    result = REGISTRY.validate_registry(data)
    assert result["active_surfaces"] == 9
    assert result["historical_surfaces"] == 3
    assert data["invariants"]["no_generic_raking_or_ipf"] is True
    assert (
        data["invariants"]["census_design_inverse_probability_is_analysis_weight"]
        is False
    )


def test_registry_has_single_authority_for_each_active_question() -> None:
    data = load()
    ids = [surface["id"] for surface in data["surfaces"]]
    assert ids == ["T-A", "T-B", "T-C", "L1", "L2", "L3", "L4", "D-1", "OBS"]
    by_id = {surface["id"]: surface for surface in data["surfaces"]}
    assert by_id["T-A"]["stage"] == "truth"
    assert by_id["T-B"]["stage"] == "within_domain_model"
    assert by_id["T-C"]["stage"] == "transport"
    assert by_id["L1"]["stage"] == "truth"
    assert by_id["L3"]["stage"] == "calibration"
    assert by_id["L4"]["stage"] == "downstream_impact"
    assert by_id["D-1"]["promotion_role"].endswith("never generates transport weights.")


def test_weight_and_calibration_semantics_do_not_collapse() -> None:
    data = load()
    by_id = {surface["id"]: surface for surface in data["surfaces"]}
    assert by_id["L1"]["weights"]["measurement"] == "PONDERA"
    assert by_id["T-A"]["weights"]["measurement"] == "PONDIH"
    assert by_id["T-B"]["calibration"]["kind"] == "nested_outer_fold_residual_ecdf"
    assert by_id["L3"]["calibration"]["kind"] == "two_logit_offsets"
    assert by_id["D-1"]["calibration"]["kind"] == "none"
    assert "design-IPW" in by_id["L3"]["weights"]["transport"]


def test_superseded_wedges_are_not_active_surfaces() -> None:
    data = load()
    active = {surface["id"] for surface in data["surfaces"]}
    historical = {item["id"]: item for item in data["superseded"]}
    assert "Q8-global-domain-classifier" not in active
    assert historical["Q8-global-domain-classifier"]["replaced_by"] == "D-1"
    assert historical["legacy-ajustar-empleo"]["status"] == "superseded"


def test_unknown_dependency_fails_closed() -> None:
    data = copy.deepcopy(load())
    data["surfaces"][0]["depends_on"] = ["DOES-NOT-EXIST"]
    with pytest.raises(REGISTRY.RegistryError, match="unknown dependencies"):
        REGISTRY.validate_registry(data)


def test_dependency_cycle_fails_closed() -> None:
    data = copy.deepcopy(load())
    by_id = {surface["id"]: surface for surface in data["surfaces"]}
    by_id["T-A"]["depends_on"] = ["T-B"]
    with pytest.raises(REGISTRY.RegistryError, match="dependency cycle"):
        REGISTRY.validate_registry(data)
