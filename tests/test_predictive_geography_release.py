import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

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
            {"household_id": household_id, "point_welfare": 120.0 + i, "estimation_status": "estimated"}
        )
    frame = root / "frame.json"
    frame.write_text(
        json.dumps({"release_id": "frame-fixture", "households": households, "persons": persons}),
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
                {"period": period, "region_id": region, "measure": measure, "value_2016_01": value}
                for region in regions
                for measure, value in (("CBA", 100.0), ("CBT", 180.0))
            ]
        ),
        encoding="utf-8",
    )
    return frame, welfare, baskets


def test_profiles_pin_governed_24_and_525_inventories():
    profiles = load_profiles()
    assert len(profiles["province_2010"]["expected_ids"]) == 24
    assert len(profiles["department_2010"]["expected_ids"]) == 525
    assert "02001" in profiles["department_2010"]["expected_ids"]
    assert all(len(value) == 5 for value in profiles["department_2010"]["expected_ids"])


@pytest.mark.parametrize(
    ("level", "field", "ids"),
    [
        ("province_2010", "province_2010_id", ["02", "06"]),
        ("department_2010", "department_2010_id", ["02001", "06028"]),
    ],
)
def test_generic_producer_emits_exact_profile_facts(level, field, ids):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        frame, welfare, baskets = _write_fixture(root, field=field, ids=ids)
        output = root / "release"
        built = build_release(
            welfare_path=welfare,
            frame_path=frame,
            baskets_path=baskets,
            method_path=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
            output=output,
            period="2024-Q3",
            geography_level=level,
            expected_geography_ids=set(ids),
            expected_households=2,
            expected_persons=2,
        )
        verify_estimate_release(built)
        rows = (built / "poverty_estimates.csv").read_text(encoding="utf-8").splitlines()
        assert len(rows) - 1 == len(ids) * 12 + 12
        manifest = json.loads((built / "release_manifest.json").read_text(encoding="utf-8"))
        assert manifest["estimation_period"] == "2024-Q3"
        assert manifest["release_id"].endswith(
            "-province-predictive-v1" if level == "province_2010" else "-department-predictive-v1"
        )


def test_department_id_must_already_be_zero_preserving_string():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        frame, welfare, baskets = _write_fixture(
            root, field="department_2010_id", ids=["02001"]
        )
        payload = json.loads(frame.read_text(encoding="utf-8"))
        payload["households"][0]["department_2010_id"] = 2001
        frame.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="numeric geography coercion is forbidden"):
            build_release(
                welfare_path=welfare,
                frame_path=frame,
                baskets_path=baskets,
                method_path=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
                output=root / "release",
                period="2024-Q3",
                geography_level="department_2010",
                expected_geography_ids={"02001"},
            )


def test_exact_inventory_rejects_missing_plus_extra_even_when_count_matches():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        frame, welfare, baskets = _write_fixture(
            root, field="department_2010_id", ids=["02001", "06028"]
        )
        with pytest.raises(ValueError, match="do not equal governed inventory"):
            build_release(
                welfare_path=welfare,
                frame_path=frame,
                baskets_path=baskets,
                method_path=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
                output=root / "release",
                period="2024-Q3",
                geography_level="department_2010",
                expected_geography_ids={"02001", "06035"},
            )


def test_basket_period_is_exact_not_q3_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        frame, welfare, baskets = _write_fixture(
            root, field="department_2010_id", ids=["02001"], period="2024-Q3"
        )
        with pytest.raises(ValueError, match="2024-Q2"):
            build_release(
                welfare_path=welfare,
                frame_path=frame,
                baskets_path=baskets,
                method_path=Path("configs/poverty_methods/indec-line-poverty-2016-v1.json"),
                output=root / "release",
                period="2024-Q2",
                geography_level="department_2010",
                expected_geography_ids={"02001"},
            )
