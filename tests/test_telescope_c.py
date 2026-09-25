from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MODULE = Path(__file__).parents[1] / "science" / "telescope_c" / "run.py"
SPEC = importlib.util.spec_from_file_location("telescope_c_run", MODULE)
assert SPEC and SPEC.loader
TC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TC
SPEC.loader.exec_module(TC)


def eph_households():
    return pd.DataFrame([
        {
            "household_id": "e0", "PONDIH": 2.0, "member_count_records": 2,
            "outer_fold": 0, "observed_welfare": 80.0, "point_welfare": 110.0,
            "household_cba": 90.0, "household_cbt": 140.0,
            "p_indigent": 0.30, "p_poor": 0.70,
        },
        {
            "household_id": "e1", "PONDIH": 3.0, "member_count_records": 2,
            "outer_fold": 1, "observed_welfare": 180.0, "point_welfare": 160.0,
            "household_cba": 100.0, "household_cbt": 150.0,
            "p_indigent": 0.10, "p_poor": 0.45,
        },
    ])


def census_households():
    rows = []
    for fold, shift in ((0, 0.0), (1, 10.0)):
        for i in range(10):
            point = 80.0 + 15.0 * i + shift
            rows.append({
                "outer_fold": fold,
                "household_id": f"c{i}",
                "member_count": 1,
                "point_welfare": point,
                "household_cba": 100.0,
                "household_cbt": 160.0,
                "p_indigent": max(0.02, min(0.95, 0.55 - point / 500.0)),
                "p_poor": max(0.05, min(0.98, 0.90 - point / 600.0)),
            })
    return pd.DataFrame(rows)


def eph_people():
    rows = []
    scores = [0.10, 0.18, 0.32, 0.45]
    for i, (hh, weight) in enumerate((("e0", 2.0), ("e0", 2.0), ("e1", 3.0), ("e1", 3.0))):
        h = eph_households().set_index("household_id").loc[hh]
        rows.append({
            "row_id": f"ep{i}", "household_id": hh, "person_weight": weight,
            "target_probability_equal_prior": scores[i], "support_weak": False,
            "observed_welfare": h.observed_welfare, "point_welfare": h.point_welfare,
            "household_cba": h.household_cba, "household_cbt": h.household_cbt,
            "p_indigent": h.p_indigent, "p_poor": h.p_poor,
        })
    return pd.DataFrame(rows)


def census_support():
    return pd.DataFrame([
        {
            "row_id": f"cp{i}", "household_id": f"c{i}",
            "target_probability_equal_prior": 0.05 + 0.09 * i,
            "support_weak": i >= 8,
        }
        for i in range(10)
    ])


FOLD_MIX = {0: 0.4, 1: 0.6}


def test_c1_transport_x_residual_identity():
    bridge, decomposition = TC.build_bridge(
        eph_households(), census_households(), FOLD_MIX
    )
    assert set(decomposition.state) == set(TC.STATES)
    for row in decomposition.itertuples():
        assert np.isclose(
            row.transport_x_residual_interaction,
            row.predictive_transport - row.point_transport,
        )
    census = bridge[
        (bridge.domain == "census")
        & (bridge.outer_fold == "aggregate")
        & (bridge.representation == "predictive")
    ]
    assert np.isclose(census.estimate.sum(), 1.0)


def test_c2_margin_contributions_reconcile_to_transport():
    bridge, decomposition = TC.build_bridge(
        eph_households(), census_households(), FOLD_MIX
    )
    _, bins = TC.build_margin_diagnostics(
        eph_households(), census_households(), FOLD_MIX
    )
    poverty_transport = bins[
        (bins.domain == "transport") & (bins.concept == "poverty")
    ]
    expected_point = (
        decomposition.set_index("state").loc["indigent", "point_transport"]
        + decomposition.set_index("state").loc["poor_non_indigent", "point_transport"]
    )
    expected_predictive = (
        decomposition.set_index("state").loc["indigent", "predictive_transport"]
        + decomposition.set_index("state").loc["poor_non_indigent", "predictive_transport"]
    )
    assert np.isclose(poverty_transport.point_contribution.sum(), expected_point)
    assert np.isclose(
        poverty_transport.predictive_contribution.sum(), expected_predictive
    )


def test_c3_support_bin_contributions_reconcile():
    table, hard, tail, cuts, tail_cut = TC.support_quintile_stats(
        eph_people(), census_support(), census_households(), FOLD_MIX
    )
    assert len(cuts) == 4
    assert 0 <= tail_cut <= 1
    target = table[(table.domain == "census") & (table.concept == "poverty")]
    source = table[(table.domain == "eph") & (table.concept == "poverty")]
    transport = table[
        (table.domain == "transport") & (table.concept == "poverty")
    ]
    assert np.isclose(target.population_share.sum(), 1.0)
    assert np.isclose(source.population_share.sum(), 1.0)
    assert np.isclose(
        transport.point_contribution.sum(),
        target.point_contribution.sum() - source.point_contribution.sum(),
    )
    assert set(hard.support_class) == {"high_support", "weak_support"}
    assert set(tail.domain) == {"eph", "census"}


def test_c4_standardization_is_bounded_diagnostic():
    bridge, _ = TC.build_bridge(eph_households(), census_households(), FOLD_MIX)
    support, _, _, cuts, _ = TC.support_quintile_stats(
        eph_people(), census_support(), census_households(), FOLD_MIX
    )
    out = TC.composition_standardization(eph_people(), support, bridge, cuts)
    assert set(out.concept) == {"indigence", "poverty"}
    assert set(out.estimable) <= {True, False}
    assert out.note.str.contains("one-dimensional").all()
