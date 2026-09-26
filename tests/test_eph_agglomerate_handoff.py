from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PF = _load(
    "augment_population_frame_agglomerate",
    "scripts/augment_population_frame_agglomerate.py",
)
RB = _load(
    "build_eph_agglomerate_region_binding",
    "scripts/build_eph_agglomerate_region_binding.py",
)


def test_population_frame_adapter_is_lossless_except_nullable_geography():
    frame = {
        "release_id": "frame-fixture",
        "households": [
            {
                "household_id": "h1",
                "department_2010_id": "02001",
                "region_id": "gran_buenos_aires",
                "analysis_weight": 1.0,
            },
            {
                "household_id": "h2",
                "department_2010_id": "50007",
                "region_id": "cuyo",
                "analysis_weight": 1.0,
            },
        ],
        "persons": [
            {"person_id": "p1", "household_id": "h1", "sex": "female", "age": 30},
            {"person_id": "p2", "household_id": "h2", "sex": "male", "age": 40},
        ],
    }
    patch = {
        "schema_version": "research.population-frame-geography-patch/v1",
        "household_key": "household_id",
        "geography_field": "eph_agglomerate_id",
        "rows": [
            {
                "household_id": "h1",
                "eph_agglomerate_id": "32",
                "mapped_to_eph_frame": True,
            },
            {
                "household_id": "h2",
                "eph_agglomerate_id": None,
                "mapped_to_eph_frame": False,
            },
        ],
    }

    out, qa = PF.augment_population_frame(frame, patch)

    assert out["persons"] == frame["persons"]
    assert out["households"][0]["eph_agglomerate_id"] == "32"
    assert out["households"][1]["eph_agglomerate_id"] is None
    assert out["households"][0]["analysis_weight"] == 1.0
    assert qa["mapped_to_eph_frame_households"] == 1
    assert qa["outside_eph_frame_households"] == 1
    assert qa["represented_eph_agglomerate_ids"] == ["32"]
    assert qa["person_payload_unchanged"] is True
    assert qa["sampling_changed"] is False
    assert qa["weights_changed"] is False
    assert qa["model_changed"] is False


def test_population_frame_adapter_requires_exact_household_identity():
    frame = {"households": [{"household_id": "h1"}], "persons": []}
    patch = {
        "schema_version": "research.population-frame-geography-patch/v1",
        "household_key": "household_id",
        "geography_field": "eph_agglomerate_id",
        "rows": [
            {
                "household_id": "other",
                "eph_agglomerate_id": "32",
                "mapped_to_eph_frame": True,
            }
        ],
    }
    with pytest.raises(PF.PopulationFrameAgglomerateError, match="identity mismatch"):
        PF.augment_population_frame(frame, patch)


def test_region_binding_reuses_telescope_a_semantics_and_requires_exact_inventory():
    q1 = pd.DataFrame(
        {
            "AGLOMERADO": ["32", "32", "33"],
            "basket_region": [
                "gran_buenos_aires",
                "gran_buenos_aires",
                "pampeana",
            ],
        }
    )
    q2 = pd.DataFrame(
        {
            "AGLOMERADO": ["32", "33"],
            "basket_region": ["gran_buenos_aires", "pampeana"],
        }
    )
    rows, qa = RB.derive_binding([q1, q2], {"32", "33"})

    assert rows == [
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
    ]
    assert qa["exact_inventory_match"] is True
    assert qa["new_poverty_computation"] is False
    assert qa["spatial_inference"] is False


def test_region_binding_fails_if_one_agglomerate_changes_region():
    q1 = pd.DataFrame(
        {
            "AGLOMERADO": ["93", "93"],
            "basket_region": ["patagonia", "pampeana"],
        }
    )
    with pytest.raises(
        RB.AgglomerateRegionBindingError,
        match="multiple basket regions",
    ):
        RB.derive_binding([q1], {"93"})
