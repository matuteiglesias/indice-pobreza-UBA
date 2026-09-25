#!/usr/bin/env python3
"""Telescope C: matched-model EPH -> Census-derived target transport microscope."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from poverty_pipeline.science import load_poverty_method

REGION_MAP = {
    1: "gran_buenos_aires",
    40: "noroeste",
    41: "noreste",
    42: "cuyo",
    43: "pampeana",
    44: "patagonia",
}
REGIONS = tuple(sorted(REGION_MAP.values()))
SEX_MAP = {1: "male", 2: "female"}
STATES = ("indigent", "poor_non_indigent", "nonpoor")
MARGIN_EDGES = np.array([-np.inf, 0.50, 0.75, 0.90, 1.00, 1.10, 1.25, 1.50, 2.00, np.inf])
MARGIN_LABELS = (
    "<=0.50", "0.50-0.75", "0.75-0.90", "0.90-1.00", "1.00-1.10",
    "1.10-1.25", "1.25-1.50", "1.50-2.00", ">2.00",
)
DEFAULT_METHOD = "configs/poverty_methods/indec-line-poverty-2016-v1.json"


class TelescopeCError(ValueError):
    pass


def require(frame: pd.DataFrame, columns, label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise TelescopeCError(f"{label} missing columns: {missing}")


def period_parts(period: str):
    try:
        year, quarter = period.upper().split("-Q")
        year, quarter = int(year), int(quarter)
    except (AttributeError, ValueError) as exc:
        raise TelescopeCError("period must be YYYY-Q1..Q4") from exc
    if quarter not in (1, 2, 3, 4):
        raise TelescopeCError("period must be YYYY-Q1..Q4")
    first_month = 1 + 3 * (quarter - 1)
    months = tuple(pd.Timestamp(year, month, 1) for month in range(first_month, first_month + 3))
    return year, quarter, months


def normalize_region(value: str) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    return {
        "patagónica": "patagonia",
        "patagonica": "patagonia",
        "gran_buenos_aires": "gran_buenos_aires",
    }.get(text, text)


def normalize_id(value) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def quarter_basket(frame: pd.DataFrame, period: str, label: str) -> dict[str, float]:
    require(frame, REGIONS, label)
    date_col = next(
        (name for name in ("indice_tiempo", "period", "date", "Fecha") if name in frame),
        None,
    )
    if date_col is None:
        raise TelescopeCError(f"{label} needs a date column")
    _, _, months = period_parts(period)
    dates = pd.to_datetime(frame[date_col], errors="coerce").dt.to_period("M").dt.to_timestamp()
    if dates.isna().any():
        raise TelescopeCError(f"{label} has bad dates")
    selected = frame.loc[dates.isin(months)].copy()
    selected["_month"] = dates[dates.isin(months)].to_numpy()
    counts = selected._month.value_counts()
    if set(counts.index) != set(months) or not (counts == 1).all():
        raise TelescopeCError(f"{label} must contain each requested month exactly once")
    out = {}
    for region in REGIONS:
        values = pd.to_numeric(selected[region], errors="coerce")
        if values.isna().any() or (values <= 0).any():
            raise TelescopeCError(f"{label} has invalid {region} values")
        out[region] = float(values.mean())
    return out


def weighted_mean(values, weights) -> float:
    values = np.asarray(values, float)
    weights = np.asarray(weights, float)
    if (
        len(values) != len(weights)
        or not len(values)
        or not np.isfinite(values).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
    ):
        raise TelescopeCError("invalid weighted mean inputs")
    return float(np.average(values, weights=weights))


def weighted_quantile(values, weights, quantiles) -> np.ndarray:
    values = np.asarray(values, float)
    weights = np.asarray(weights, float)
    quantiles = np.asarray(quantiles, float)
    if (
        len(values) != len(weights)
        or not len(values)
        or not np.isfinite(values).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
        or (quantiles < 0).any()
        or (quantiles > 1).any()
    ):
        raise TelescopeCError("invalid weighted quantile inputs")
    order = np.argsort(values, kind="stable")
    v, w = values[order], weights[order]
    centers = (np.cumsum(w) - 0.5 * w) / w.sum()
    return np.interp(quantiles, centers, v, left=v[0], right=v[-1])


def ecdf_probability(residuals, cut) -> np.ndarray:
    residuals = np.sort(np.asarray(residuals, float))
    cut = np.asarray(cut, float)
    if not len(residuals) or not np.isfinite(residuals).all() or not np.isfinite(cut).all():
        raise TelescopeCError("invalid residual ECDF inputs")
    return np.searchsorted(residuals, cut, side="right") / len(residuals)


def state_probabilities(frame: pd.DataFrame, representation: str) -> dict[str, np.ndarray]:
    if representation == "point":
        indigent = (frame.point_welfare <= frame.household_cba).astype(float).to_numpy()
        poor = (frame.point_welfare <= frame.household_cbt).astype(float).to_numpy()
    elif representation == "predictive":
        indigent = frame.p_indigent.to_numpy(float)
        poor = frame.p_poor.to_numpy(float)
    elif representation == "observed":
        require(frame, ["observed_welfare"], "observed frame")
        indigent = (frame.observed_welfare <= frame.household_cba).astype(float).to_numpy()
        poor = (frame.observed_welfare <= frame.household_cbt).astype(float).to_numpy()
    else:
        raise TelescopeCError(f"unknown representation {representation}")
    pni = poor - indigent
    nonpoor = 1.0 - poor
    if (pni < -1e-12).any() or (nonpoor < -1e-12).any():
        raise TelescopeCError(f"invalid state probabilities for {representation}")
    return {
        "indigent": np.clip(indigent, 0, 1),
        "poor_non_indigent": np.clip(pni, 0, 1),
        "nonpoor": np.clip(nonpoor, 0, 1),
    }


def concept_probability(frame: pd.DataFrame, representation: str, concept: str) -> np.ndarray:
    states = state_probabilities(frame, representation)
    if concept == "indigence":
        return states["indigent"]
    if concept == "poverty":
        return states["indigent"] + states["poor_non_indigent"]
    raise TelescopeCError(f"unknown concept {concept}")


def regional_lines_from_telescope_b(
    telescope_b_households: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, float]]:
    require(
        telescope_b_households,
        ["basket_region", "cba_per_ae", "cbt_per_ae"],
        "Telescope-B regional lines",
    )
    frame = telescope_b_households[["basket_region", "cba_per_ae", "cbt_per_ae"]].copy()
    frame["basket_region"] = frame.basket_region.map(normalize_region)
    frame["cba_per_ae"] = pd.to_numeric(frame.cba_per_ae, errors="coerce")
    frame["cbt_per_ae"] = pd.to_numeric(frame.cbt_per_ae, errors="coerce")
    if frame[["cba_per_ae", "cbt_per_ae"]].isna().any().any():
        raise TelescopeCError("Telescope-B regional lines must be numeric")
    cba, cbt = {}, {}
    for region in REGIONS:
        rows = frame[frame.basket_region == region]
        if rows.empty:
            raise TelescopeCError(f"Telescope-B artifact missing regional line {region}")
        cba_values = rows.cba_per_ae.unique()
        cbt_values = rows.cbt_per_ae.unique()
        if len(cba_values) != 1 or len(cbt_values) != 1:
            raise TelescopeCError(f"Telescope-B regional line is not unique for {region}")
        cba[region], cbt[region] = float(cba_values[0]), float(cbt_values[0])
        if cba[region] <= 0 or cba[region] > cbt[region]:
            raise TelescopeCError(f"invalid Telescope-B regional line for {region}")
    return cba, cbt


def build_census_lines(
    census_p1: pd.DataFrame,
    selection: pd.DataFrame,
    department_region: pd.DataFrame,
    cba: dict[str, float],
    cbt: dict[str, float],
    *,
    method_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require(census_p1, ["row_id", "household_id", "P02", "P03"], "Census P1")
    if census_p1.row_id.duplicated().any():
        raise TelescopeCError("duplicate Census person row_id")
    person = census_p1[["row_id", "household_id", "P02", "P03"]].copy()
    sex = pd.to_numeric(person.P02, errors="coerce").map(SEX_MAP)
    age = pd.to_numeric(person.P03, errors="coerce")
    if sex.isna().any() or age.isna().any() or ((age % 1) != 0).any() or (age < 0).any():
        raise TelescopeCError("invalid Census sex/age for adult equivalence")
    method = load_poverty_method(method_path)
    person["adult_equivalent"] = [
        method.adult_equivalence(sex=s, age=int(a)) for s, a in zip(sex, age)
    ]
    grouped = person.groupby("household_id", sort=False).agg(
        member_count=("row_id", "size"),
        adult_equivalents=("adult_equivalent", "sum"),
    )

    hh_key = next(
        (name for name in ("sample_household_id", "household_id") if name in selection),
        None,
    )
    dep_key = next(
        (name for name in ("department_id", "DPTO") if name in selection),
        None,
    )
    if hh_key is None or dep_key is None:
        raise TelescopeCError("Census selection needs household and department IDs")
    select = selection[[hh_key, dep_key]].copy()
    select["household_id"] = select[hh_key].astype(str)
    select["department_id"] = select[dep_key].map(normalize_id)
    if select.household_id.duplicated().any():
        raise TelescopeCError("duplicate Census selection household_id")
    if set(grouped.index) != set(select.household_id):
        missing = sorted(set(grouped.index) - set(select.household_id))[:20]
        extra = sorted(set(select.household_id) - set(grouped.index))[:20]
        raise TelescopeCError(
            f"Census P1/selection household mismatch missing={missing} extra={extra}"
        )

    dep_col = next(
        (name for name in ("DPTO", "department_id") if name in department_region),
        None,
    )
    reg_col = next(
        (name for name in ("Region", "region") if name in department_region),
        None,
    )
    if dep_col is None or reg_col is None:
        raise TelescopeCError("department-region binding needs department and region columns")
    binding = department_region[[dep_col, reg_col]].copy()
    binding["department_id"] = binding[dep_col].map(normalize_id)
    binding["basket_region"] = binding[reg_col].map(normalize_region)
    if binding.department_id.duplicated().any():
        contradictory = binding.groupby("department_id").basket_region.nunique()
        if (contradictory > 1).any():
            raise TelescopeCError("department maps to multiple basket regions")
        binding = binding.drop_duplicates("department_id")
    region_map = binding.set_index("department_id").basket_region

    hh = grouped.reset_index().merge(
        select[["household_id", "department_id"]],
        on="household_id",
        validate="one_to_one",
    )
    hh["basket_region"] = hh.department_id.map(region_map)
    if hh.basket_region.isna().any():
        raise TelescopeCError(
            f"unmapped Census departments: {sorted(hh.loc[hh.basket_region.isna(),'department_id'].unique())[:20]}"
        )
    unknown = sorted(set(hh.basket_region) - set(REGIONS))
    if unknown:
        raise TelescopeCError(f"unknown Census basket regions: {unknown}")

    hh["cba_per_ae"] = hh.basket_region.map(cba)
    hh["cbt_per_ae"] = hh.basket_region.map(cbt)
    hh["household_cba"] = hh.adult_equivalents * hh.cba_per_ae
    hh["household_cbt"] = hh.adult_equivalents * hh.cbt_per_ae
    if (hh.household_cba <= 0).any() or (hh.household_cba > hh.household_cbt).any():
        raise TelescopeCError("invalid Census household poverty lines")
    return hh, person[["row_id", "household_id"]].copy()


def build_eph_validation(
    telescope_b_households: pd.DataFrame,
    eph_persons: pd.DataFrame,
    eph_matched_person_scores: pd.DataFrame,
    eph_support_scores: pd.DataFrame,
    fold_residuals: pd.DataFrame,
    *,
    period: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, float]]:
    hh = telescope_b_households.copy()
    require(
        hh,
        [
            "household_id", "member_count_records", "PONDIH", "observed_welfare",
            "point_welfare", "outer_fold", "household_cba", "household_cbt",
            "p_indigent", "p_poor",
        ],
        "Telescope-B households",
    )
    if hh.household_id.duplicated().any():
        raise TelescopeCError("duplicate Telescope-B household_id")
    for name in (
        "member_count_records", "PONDIH", "observed_welfare", "point_welfare",
        "outer_fold", "household_cba", "household_cbt", "p_indigent", "p_poor",
    ):
        hh[name] = pd.to_numeric(hh[name], errors="coerce")
    if hh[[
        "member_count_records", "PONDIH", "observed_welfare", "point_welfare",
        "outer_fold", "household_cba", "household_cbt", "p_indigent", "p_poor",
    ]].isna().any().any():
        raise TelescopeCError("Telescope-B household fields must be numeric/complete")
    if (hh.PONDIH <= 0).any():
        raise TelescopeCError("Telescope-C EPH cohort requires positive PONDIH")

    year, quarter, _ = period_parts(period)
    people = eph_persons.copy()
    require(
        people,
        ["CODUSU", "NRO_HOGAR", "COMPONENTE", "ANO4", "TRIMESTRE"],
        "EPH persons",
    )
    for name in ("CODUSU", "NRO_HOGAR", "COMPONENTE", "ANO4", "TRIMESTRE"):
        people[name] = people[name].astype(str).str.strip()
    y = pd.to_numeric(people.ANO4, errors="coerce")
    q = pd.to_numeric(people.TRIMESTRE, errors="coerce")
    if y.isna().any() or q.isna().any() or set(zip(y.astype(int), q.astype(int))) != {(year, quarter)}:
        raise TelescopeCError("EPH person period mismatch")
    people["row_id"] = people.CODUSU + ":" + people.NRO_HOGAR + ":" + people.COMPONENTE
    people["household_id"] = (
        people.ANO4 + ":" + people.TRIMESTRE + ":" + people.CODUSU + ":" + people.NRO_HOGAR
    )
    selected = people[people.household_id.isin(set(hh.household_id))][
        ["row_id", "household_id"]
    ].copy()
    if len(selected) != int(hh.member_count_records.sum()):
        raise TelescopeCError("EPH selected person count does not match Telescope B")

    require(eph_matched_person_scores, ["row_id", "outer_fold", "pred"], "EPH matched scores")
    matched = selected.merge(
        eph_matched_person_scores[["row_id", "outer_fold", "pred"]],
        on="row_id",
        how="left",
        validate="one_to_one",
    )
    if matched[["outer_fold", "pred"]].isna().any().any():
        raise TelescopeCError("matched EPH scores do not cover Telescope-B persons")
    agg = matched.groupby("household_id").agg(
        reproduced_point=("pred", "sum"),
        reproduced_fold=("outer_fold", "first"),
        fold_count=("outer_fold", "nunique"),
    )
    check = hh.set_index("household_id").join(agg)
    if (check.fold_count != 1).any():
        raise TelescopeCError("matched EPH household crosses outer folds")
    if not np.allclose(check.point_welfare, check.reproduced_point, rtol=1e-10, atol=1e-7):
        raise TelescopeCError("matched outer models do not reproduce Telescope-B household point welfare")
    if not np.array_equal(check.outer_fold.astype(int), check.reproduced_fold.astype(int)):
        raise TelescopeCError("matched EPH fold differs from Telescope B")

    require(fold_residuals, ["outer_fold", "residual"], "fold residuals")
    residuals = fold_residuals.copy()
    residuals["outer_fold"] = pd.to_numeric(residuals.outer_fold, errors="coerce")
    residuals["residual"] = pd.to_numeric(residuals.residual, errors="coerce")
    if residuals.isna().any().any():
        raise TelescopeCError("invalid fold residual table")
    for fold in sorted(hh.outer_fold.astype(int).unique()):
        mask = hh.outer_fold.astype(int) == fold
        r = residuals.loc[residuals.outer_fold.astype(int) == fold, "residual"].to_numpy(float)
        pi = ecdf_probability(
            r, hh.loc[mask, "household_cba"].to_numpy(float) - hh.loc[mask, "point_welfare"].to_numpy(float)
        )
        pp = ecdf_probability(
            r, hh.loc[mask, "household_cbt"].to_numpy(float) - hh.loc[mask, "point_welfare"].to_numpy(float)
        )
        if not np.allclose(pi, hh.loc[mask, "p_indigent"].to_numpy(float), atol=1e-12, rtol=0):
            raise TelescopeCError("Telescope-B indigence probabilities do not reproduce from G_-f")
        if not np.allclose(pp, hh.loc[mask, "p_poor"].to_numpy(float), atol=1e-12, rtol=0):
            raise TelescopeCError("Telescope-B poverty probabilities do not reproduce from G_-f")

    require(
        eph_support_scores,
        ["row_id", "target_probability_equal_prior", "support_weak"],
        "EPH support scores",
    )
    eph_people = selected.merge(
        eph_support_scores[["row_id", "target_probability_equal_prior", "support_weak"]],
        on="row_id",
        how="left",
        validate="one_to_one",
    )
    if eph_people[["target_probability_equal_prior", "support_weak"]].isna().any().any():
        raise TelescopeCError("EPH support scores do not cover Telescope-B persons")
    eph_people = eph_people.merge(
        hh[[
            "household_id", "PONDIH", "observed_welfare", "point_welfare",
            "outer_fold", "household_cba", "household_cbt", "p_indigent", "p_poor",
        ]],
        on="household_id",
        validate="many_to_one",
    )
    eph_people["person_weight"] = eph_people.PONDIH.astype(float)

    fold_mass = (
        hh.assign(_mass=hh.PONDIH * hh.member_count_records)
        .groupby(hh.outer_fold.astype(int))._mass.sum()
    )
    fold_mix = (fold_mass / fold_mass.sum()).to_dict()
    if not math.isclose(sum(fold_mix.values()), 1.0, abs_tol=1e-12):
        raise TelescopeCError("EPH fold person-weight mix does not sum to one")
    return hh, eph_people, {int(k): float(v) for k, v in fold_mix.items()}


def build_census_matched(
    census_households: pd.DataFrame,
    census_people: pd.DataFrame,
    census_matched_person_scores: pd.DataFrame,
    census_support_scores: pd.DataFrame,
    fold_residuals: pd.DataFrame,
    fold_mix: dict[int, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require(
        census_matched_person_scores,
        ["row_id", "household_id", "outer_fold", "pred"],
        "Census matched scores",
    )
    scores = census_matched_person_scores.copy()
    scores["outer_fold"] = pd.to_numeric(scores.outer_fold, errors="coerce")
    scores["pred"] = pd.to_numeric(scores.pred, errors="coerce")
    if scores[["outer_fold", "pred"]].isna().any().any():
        raise TelescopeCError("invalid Census matched scores")
    if set(scores.outer_fold.astype(int).unique()) != set(fold_mix):
        raise TelescopeCError("Census matched folds do not equal EPH fold mix")
    expected_persons = len(census_people)
    counts = scores.groupby(scores.outer_fold.astype(int)).size()
    if not (counts == expected_persons).all():
        raise TelescopeCError("each matched outer model must score all Census persons")
    if scores.duplicated(["outer_fold", "row_id"]).any():
        raise TelescopeCError("duplicate Census matched fold/person score")

    hh_scores = scores.groupby(["outer_fold", "household_id"], sort=False).agg(
        point_welfare=("pred", "sum"),
        scored_members=("row_id", "size"),
    ).reset_index()
    hh = hh_scores.merge(
        census_households,
        on="household_id",
        validate="many_to_one",
    )
    if not (hh.scored_members.astype(int) == hh.member_count.astype(int)).all():
        raise TelescopeCError("Census matched scoring membership mismatch")
    if hh.groupby("outer_fold").household_id.nunique().nunique() != 1:
        raise TelescopeCError("outer models do not cover the same Census households")

    residuals = fold_residuals.copy()
    residuals["outer_fold"] = pd.to_numeric(residuals.outer_fold, errors="coerce").astype(int)
    residuals["residual"] = pd.to_numeric(residuals.residual, errors="coerce")
    hh["p_indigent"] = np.nan
    hh["p_poor"] = np.nan
    for fold in sorted(fold_mix):
        mask = hh.outer_fold.astype(int) == fold
        r = residuals.loc[residuals.outer_fold == fold, "residual"].to_numpy(float)
        if not len(r):
            raise TelescopeCError(f"missing G_-f residual ECDF for fold {fold}")
        mu = hh.loc[mask, "point_welfare"].to_numpy(float)
        hh.loc[mask, "p_indigent"] = ecdf_probability(
            r, hh.loc[mask, "household_cba"].to_numpy(float) - mu
        )
        hh.loc[mask, "p_poor"] = ecdf_probability(
            r, hh.loc[mask, "household_cbt"].to_numpy(float) - mu
        )
    if hh[["p_indigent", "p_poor"]].isna().any().any():
        raise TelescopeCError("Census predictive probabilities incomplete")
    if (hh.p_indigent > hh.p_poor + 1e-15).any():
        raise TelescopeCError("Census predictive indigence exceeds poverty")

    require(
        census_support_scores,
        ["row_id", "household_id", "target_probability_equal_prior", "support_weak"],
        "Census support scores",
    )
    support = census_people.merge(
        census_support_scores[[
            "row_id", "household_id", "target_probability_equal_prior", "support_weak"
        ]],
        on=["row_id", "household_id"],
        how="left",
        validate="one_to_one",
    )
    if support[["target_probability_equal_prior", "support_weak"]].isna().any().any():
        raise TelescopeCError("Census support scores incomplete")
    return hh, support


def estimate_state_rows(
    frame: pd.DataFrame,
    weights,
    *,
    domain: str,
    representation: str,
    outer_fold,
) -> list[dict]:
    probs = state_probabilities(frame, representation)
    weights = np.asarray(weights, float)
    rows = []
    estimates = {}
    for state in STATES:
        estimate = weighted_mean(probs[state], weights)
        estimates[state] = estimate
        rows.append({
            "domain": domain,
            "representation": representation,
            "outer_fold": outer_fold,
            "state": state,
            "estimate": estimate,
            "weighted_numerator": float(np.dot(probs[state], weights)),
            "weighted_denominator": float(weights.sum()),
        })
    if not math.isclose(sum(estimates.values()), 1.0, abs_tol=1e-12):
        raise TelescopeCError(f"{domain}/{representation} states do not sum to one")
    return rows


def build_bridge(
    eph_hh: pd.DataFrame,
    census_hh: pd.DataFrame,
    fold_mix: dict[int, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    eph_weights = eph_hh.PONDIH.to_numpy(float) * eph_hh.member_count_records.to_numpy(float)
    rows.extend(estimate_state_rows(
        eph_hh, eph_weights, domain="eph", representation="observed", outer_fold="aggregate"
    ))
    rows.extend(estimate_state_rows(
        eph_hh, eph_weights, domain="eph", representation="point", outer_fold="aggregate"
    ))
    rows.extend(estimate_state_rows(
        eph_hh, eph_weights, domain="eph", representation="predictive", outer_fold="aggregate"
    ))

    for fold, mix in sorted(fold_mix.items()):
        e = eph_hh[eph_hh.outer_fold.astype(int) == fold]
        ew = e.PONDIH.to_numpy(float) * e.member_count_records.to_numpy(float)
        rows.extend(estimate_state_rows(
            e, ew, domain="eph", representation="point", outer_fold=fold
        ))
        rows.extend(estimate_state_rows(
            e, ew, domain="eph", representation="predictive", outer_fold=fold
        ))
        c = census_hh[census_hh.outer_fold.astype(int) == fold]
        cw = c.member_count.to_numpy(float)
        rows.extend(estimate_state_rows(
            c, cw, domain="census", representation="point", outer_fold=fold
        ))
        rows.extend(estimate_state_rows(
            c, cw, domain="census", representation="predictive", outer_fold=fold
        ))

    bridge = pd.DataFrame(rows)

    census_aggregate = []
    for representation in ("point", "predictive"):
        for state in STATES:
            per_fold = bridge[
                (bridge.domain == "census")
                & (bridge.representation == representation)
                & (bridge.state == state)
                & (bridge.outer_fold != "aggregate")
            ].copy()
            by = {int(row.outer_fold): float(row.estimate) for row in per_fold.itertuples()}
            estimate = sum(fold_mix[fold] * by[fold] for fold in fold_mix)
            census_aggregate.append({
                "domain": "census",
                "representation": representation,
                "outer_fold": "aggregate",
                "state": state,
                "estimate": estimate,
                "weighted_numerator": np.nan,
                "weighted_denominator": np.nan,
            })
    bridge = pd.concat([bridge, pd.DataFrame(census_aggregate)], ignore_index=True)

    def get(domain, representation, state):
        row = bridge[
            (bridge.domain == domain)
            & (bridge.representation == representation)
            & (bridge.outer_fold == "aggregate")
            & (bridge.state == state)
        ]
        if len(row) != 1:
            raise TelescopeCError(f"bridge lookup failed {domain}/{representation}/{state}")
        return float(row.estimate.iloc[0])

    decomposition = []
    for state in STATES:
        ep = get("eph", "point", state)
        er = get("eph", "predictive", state)
        cp = get("census", "point", state)
        cr = get("census", "predictive", state)
        interaction = (cr - cp) - (er - ep)
        if not math.isclose(interaction, (cr - er) - (cp - ep), abs_tol=1e-12):
            raise TelescopeCError("transport x residual identity failed")
        decomposition.append({
            "state": state,
            "eph_observed": get("eph", "observed", state),
            "eph_point": ep,
            "eph_predictive": er,
            "census_point": cp,
            "census_predictive": cr,
            "point_transport": cp - ep,
            "predictive_transport": cr - er,
            "eph_residual_effect": er - ep,
            "census_residual_effect": cr - cp,
            "transport_x_residual_interaction": interaction,
        })
    return bridge, pd.DataFrame(decomposition)


def aggregate_census_long_weights(census_hh: pd.DataFrame, fold_mix: dict[int, float]) -> np.ndarray:
    return (
        census_hh.member_count.to_numpy(float)
        * census_hh.outer_fold.astype(int).map(fold_mix).to_numpy(float)
    )


def margin_rows_for_domain(
    frame: pd.DataFrame,
    weights,
    *,
    domain: str,
    concept: str,
) -> tuple[list[dict], list[dict]]:
    line_col = "household_cba" if concept == "indigence" else "household_cbt"
    line = frame[line_col].to_numpy(float)
    mu = frame.point_welfare.to_numpy(float)
    prob = frame.p_indigent.to_numpy(float) if concept == "indigence" else frame.p_poor.to_numpy(float)
    weights = np.asarray(weights, float)
    ratio = mu / line
    margin = line - mu
    values = {
        "point_welfare": mu,
        "line": line,
        "mu_over_line": ratio,
        "line_minus_mu": margin,
        "predictive_probability": prob,
    }
    qs = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    summary = []
    for variable, array in values.items():
        qv = weighted_quantile(array, weights, qs)
        summary.extend({
            "domain": domain,
            "concept": concept,
            "variable": variable,
            "quantile": q,
            "value": float(value),
        } for q, value in zip(qs, qv))

    bins = pd.cut(
        ratio,
        bins=MARGIN_EDGES,
        labels=MARGIN_LABELS,
        include_lowest=True,
        right=True,
    )
    total = float(weights.sum())
    point = (mu <= line).astype(float)
    detail = []
    for label in MARGIN_LABELS:
        mask = np.asarray(bins == label)
        mass = float(weights[mask].sum())
        if mass == 0:
            detail.append({
                "domain": domain, "concept": concept, "margin_bin": label,
                "weight_mass": 0.0, "population_share": 0.0,
                "point_rate": None, "predictive_rate": None,
                "point_contribution": 0.0, "predictive_contribution": 0.0,
            })
            continue
        point_num = float(np.dot(weights[mask], point[mask]))
        pred_num = float(np.dot(weights[mask], prob[mask]))
        detail.append({
            "domain": domain, "concept": concept, "margin_bin": label,
            "weight_mass": mass, "population_share": mass / total,
            "point_rate": point_num / mass, "predictive_rate": pred_num / mass,
            "point_contribution": point_num / total,
            "predictive_contribution": pred_num / total,
        })
    return summary, detail


def build_margin_diagnostics(
    eph_hh: pd.DataFrame,
    census_hh: pd.DataFrame,
    fold_mix: dict[int, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eph_weights = eph_hh.PONDIH.to_numpy(float) * eph_hh.member_count_records.to_numpy(float)
    census_weights = aggregate_census_long_weights(census_hh, fold_mix)
    summary_rows, detail_rows = [], []
    for concept in ("indigence", "poverty"):
        for frame, weights, domain in (
            (eph_hh, eph_weights, "eph"),
            (census_hh, census_weights, "census"),
        ):
            s, d = margin_rows_for_domain(frame, weights, domain=domain, concept=concept)
            summary_rows.extend(s)
            detail_rows.extend(d)
    detail = pd.DataFrame(detail_rows)
    transport = []
    for concept in ("indigence", "poverty"):
        for label in MARGIN_LABELS:
            e = detail[(detail.domain == "eph") & (detail.concept == concept) & (detail.margin_bin == label)].iloc[0]
            c = detail[(detail.domain == "census") & (detail.concept == concept) & (detail.margin_bin == label)].iloc[0]
            transport.append({
                "domain": "transport",
                "concept": concept,
                "margin_bin": label,
                "weight_mass": np.nan,
                "population_share": float(c.population_share - e.population_share),
                "point_rate": np.nan,
                "predictive_rate": np.nan,
                "point_contribution": float(c.point_contribution - e.point_contribution),
                "predictive_contribution": float(c.predictive_contribution - e.predictive_contribution),
            })
    detail = pd.concat([detail, pd.DataFrame(transport)], ignore_index=True)
    return pd.DataFrame(summary_rows), detail


def assign_support_bins(scores: pd.Series, cutpoints: np.ndarray) -> np.ndarray:
    return np.searchsorted(cutpoints, scores.to_numpy(float), side="right") + 1


def support_quintile_stats(
    eph_people: pd.DataFrame,
    census_support: pd.DataFrame,
    census_hh: pd.DataFrame,
    fold_mix: dict[int, float],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray, float]:
    target_scores = census_support.target_probability_equal_prior.astype(float)
    cutpoints = target_scores.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy(float)
    tail_cut = float(target_scores.quantile(0.95))
    eph = eph_people.copy()
    target = census_support.copy()
    eph["support_bin"] = assign_support_bins(eph.target_probability_equal_prior, cutpoints)
    target["support_bin"] = assign_support_bins(target.target_probability_equal_prior, cutpoints)
    eph["weakest5"] = eph.target_probability_equal_prior >= tail_cut
    target["weakest5"] = target.target_probability_equal_prior >= tail_cut

    rows = []
    eph_total = float(eph.person_weight.sum())
    for concept in ("indigence", "poverty"):
        for support_bin in range(1, 6):
            mask = eph.support_bin == support_bin
            mass = float(eph.loc[mask, "person_weight"].sum())
            if mass == 0:
                point_rate = pred_rate = np.nan
                point_contribution = pred_contribution = 0.0
            else:
                point_values = concept_probability(eph.loc[mask], "point", concept)
                pred_values = concept_probability(eph.loc[mask], "predictive", concept)
                w = eph.loc[mask, "person_weight"].to_numpy(float)
                point_rate = weighted_mean(point_values, w)
                pred_rate = weighted_mean(pred_values, w)
                point_contribution = float(np.dot(point_values, w) / eph_total)
                pred_contribution = float(np.dot(pred_values, w) / eph_total)
            rows.append({
                "domain": "eph", "concept": concept, "support_bin": support_bin,
                "population_share": mass / eph_total,
                "point_rate": point_rate, "predictive_rate": pred_rate,
                "point_contribution": point_contribution,
                "predictive_contribution": pred_contribution,
            })

    census_total = float(len(target))
    census_acc = {
        (concept, support_bin): {"mass": 0.0, "point_num": 0.0, "pred_num": 0.0}
        for concept in ("indigence", "poverty") for support_bin in range(1, 6)
    }
    for fold, mix in sorted(fold_mix.items()):
        h = census_hh[census_hh.outer_fold.astype(int) == fold][
            ["household_id", "point_welfare", "household_cba", "household_cbt", "p_indigent", "p_poor"]
        ]
        panel = target[["household_id", "support_bin"]].merge(
            h, on="household_id", validate="many_to_one"
        )
        weight = float(mix)
        for concept in ("indigence", "poverty"):
            point_values = concept_probability(panel, "point", concept)
            pred_values = concept_probability(panel, "predictive", concept)
            for support_bin in range(1, 6):
                mask = panel.support_bin.to_numpy() == support_bin
                acc = census_acc[(concept, support_bin)]
                acc["mass"] += weight * float(mask.sum())
                acc["point_num"] += weight * float(point_values[mask].sum())
                acc["pred_num"] += weight * float(pred_values[mask].sum())
    for concept in ("indigence", "poverty"):
        for support_bin in range(1, 6):
            acc = census_acc[(concept, support_bin)]
            mass = acc["mass"]
            rows.append({
                "domain": "census", "concept": concept, "support_bin": support_bin,
                "population_share": mass / census_total,
                "point_rate": acc["point_num"] / mass if mass else np.nan,
                "predictive_rate": acc["pred_num"] / mass if mass else np.nan,
                "point_contribution": acc["point_num"] / census_total,
                "predictive_contribution": acc["pred_num"] / census_total,
            })

    table = pd.DataFrame(rows)
    transport = []
    for concept in ("indigence", "poverty"):
        for support_bin in range(1, 6):
            e = table[(table.domain == "eph") & (table.concept == concept) & (table.support_bin == support_bin)].iloc[0]
            c = table[(table.domain == "census") & (table.concept == concept) & (table.support_bin == support_bin)].iloc[0]
            transport.append({
                "domain": "transport", "concept": concept, "support_bin": support_bin,
                "population_share": float(c.population_share - e.population_share),
                "point_rate": np.nan, "predictive_rate": np.nan,
                "point_contribution": float(c.point_contribution - e.point_contribution),
                "predictive_contribution": float(c.predictive_contribution - e.predictive_contribution),
            })
    table = pd.concat([table, pd.DataFrame(transport)], ignore_index=True)

    hard_rows = []
    for weak_value, label in ((False, "high_support"), (True, "weak_support")):
        people = target[target.support_weak.astype(bool) == weak_value]
        total_mass = float(len(target))
        for concept in ("indigence", "poverty"):
            point_num = pred_num = 0.0
            mass = 0.0
            for fold, mix in sorted(fold_mix.items()):
                h = census_hh[census_hh.outer_fold.astype(int) == fold][
                    ["household_id", "point_welfare", "household_cba", "household_cbt", "p_indigent", "p_poor"]
                ]
                panel = people[["household_id"]].merge(h, on="household_id", validate="many_to_one")
                point_num += mix * float(concept_probability(panel, "point", concept).sum())
                pred_num += mix * float(concept_probability(panel, "predictive", concept).sum())
                mass += mix * len(panel)
            hard_rows.append({
                "support_class": label, "concept": concept,
                "population_share": mass / total_mass,
                "point_rate": point_num / mass if mass else np.nan,
                "predictive_rate": pred_num / mass if mass else np.nan,
                "point_contribution": point_num / total_mass,
                "predictive_contribution": pred_num / total_mass,
            })

    tail_rows = []
    for domain, people in (("eph", eph), ("census", target)):
        subset = people[people.weakest5]
        for concept in ("indigence", "poverty"):
            if domain == "eph":
                weights = subset.person_weight.to_numpy(float)
                total = float(eph.person_weight.sum())
                point = concept_probability(subset, "point", concept)
                pred = concept_probability(subset, "predictive", concept)
                mass = float(weights.sum())
                point_num = float(np.dot(point, weights))
                pred_num = float(np.dot(pred, weights))
            else:
                total = float(len(target))
                point_num = pred_num = mass = 0.0
                for fold, mix in sorted(fold_mix.items()):
                    h = census_hh[census_hh.outer_fold.astype(int) == fold][
                        ["household_id", "point_welfare", "household_cba", "household_cbt", "p_indigent", "p_poor"]
                    ]
                    panel = subset[["household_id"]].merge(h, on="household_id", validate="many_to_one")
                    point_num += mix * float(concept_probability(panel, "point", concept).sum())
                    pred_num += mix * float(concept_probability(panel, "predictive", concept).sum())
                    mass += mix * len(panel)
            tail_rows.append({
                "domain": domain, "concept": concept, "threshold": tail_cut,
                "population_share": mass / total if total else np.nan,
                "point_rate": point_num / mass if mass else np.nan,
                "predictive_rate": pred_num / mass if mass else np.nan,
                "point_contribution": point_num / total if total else np.nan,
                "predictive_contribution": pred_num / total if total else np.nan,
            })
    return table, pd.DataFrame(hard_rows), pd.DataFrame(tail_rows), cutpoints, tail_cut


def composition_standardization(
    eph_people: pd.DataFrame,
    support_bins: pd.DataFrame,
    bridge: pd.DataFrame,
    cutpoints: np.ndarray,
) -> pd.DataFrame:
    eph = eph_people.copy()
    eph["support_bin"] = assign_support_bins(eph.target_probability_equal_prior, cutpoints)
    target_shares = {
        int(row.support_bin): float(row.population_share)
        for row in support_bins[
            (support_bins.domain == "census")
            & (support_bins.concept == "poverty")
        ].itertuples()
    }
    rows = []
    for concept in ("indigence", "poverty"):
        source_rates = {}
        for support_bin in range(1, 6):
            group = eph[eph.support_bin == support_bin]
            if group.empty or group.person_weight.sum() <= 0:
                source_rates[support_bin] = None
                continue
            observed = concept_probability(group, "observed", concept)
            source_rates[support_bin] = weighted_mean(observed, group.person_weight)
        estimable = all(source_rates[b] is not None and b in target_shares for b in range(1, 6))
        standardized = (
            sum(target_shares[b] * source_rates[b] for b in range(1, 6))
            if estimable else None
        )
        observed_global = weighted_mean(
            concept_probability(eph, "observed", concept), eph.person_weight
        )
        state = "indigent" if concept == "indigence" else None
        if concept == "indigence":
            point = bridge[
                (bridge.domain == "census") & (bridge.representation == "point")
                & (bridge.outer_fold == "aggregate") & (bridge.state == "indigent")
            ].estimate.iloc[0]
            predictive = bridge[
                (bridge.domain == "census") & (bridge.representation == "predictive")
                & (bridge.outer_fold == "aggregate") & (bridge.state == "indigent")
            ].estimate.iloc[0]
        else:
            point_rows = bridge[
                (bridge.domain == "census") & (bridge.representation == "point")
                & (bridge.outer_fold == "aggregate")
                & (bridge.state.isin(["indigent", "poor_non_indigent"]))
            ]
            pred_rows = bridge[
                (bridge.domain == "census") & (bridge.representation == "predictive")
                & (bridge.outer_fold == "aggregate")
                & (bridge.state.isin(["indigent", "poor_non_indigent"]))
            ]
            point = float(point_rows.estimate.sum())
            predictive = float(pred_rows.estimate.sum())
        rows.append({
            "concept": concept,
            "estimable": estimable,
            "eph_observed": observed_global,
            "eph_observed_standardized_to_census_support_mix": standardized,
            "composition_shift_on_support_axis": None if standardized is None else standardized - observed_global,
            "census_matched_point": float(point),
            "census_matched_predictive": float(predictive),
            "remaining_point_minus_standardized": None if standardized is None else float(point) - standardized,
            "note": "coarse one-dimensional standardization on cross-fitted overlap score quintiles only",
        })
    return pd.DataFrame(rows)


def render_report(summary: dict) -> str:
    lines = [
        f"# Telescope C — {summary['period']}",
        "",
        "> Research transport validation only; not official INDEC statistics.",
        "",
        "## C0 matched-model contract",
        f"- EPH validation households: {summary['c0']['eph_households']}",
        f"- EPH validation persons: {summary['c0']['eph_persons']}",
        f"- Census target households: {summary['c0']['census_households']}",
        f"- Census target persons: {summary['c0']['census_persons']}",
        "- primary estimand: persons",
        "- same five P1-R outer models and same five nested Q7 residual ECDFs",
        "",
        "## C1 aggregate transport",
        "",
        "| State | EPH point | EPH predictive | Census point | Census predictive | Point transport | Predictive transport | Transport x residual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["transport_decomposition"]:
        lines.append(
            f"| {row['state']} | {row['eph_point']:.6f} | {row['eph_predictive']:.6f} | "
            f"{row['census_point']:.6f} | {row['census_predictive']:.6f} | "
            f"{row['point_transport']:+.6f} | {row['predictive_transport']:+.6f} | "
            f"{row['transport_x_residual_interaction']:+.6f} |"
        )
    lines += [
        "",
        "C2 decomposes these movements by the household point-welfare / poverty-line margin.",
        "C3 decomposes them by cross-fitted EPH-vs-Census support.",
        "C4 is a coarse diagnostic standardization only; it is not a production transport weight.",
        "",
        "The Census target is a governed Census-derived target-year sample: department-level person mass is updated, while within-department donor-frame composition remains an explicit assumption.",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict:
    b_hh = pd.read_parquet(args.telescope_b_households)
    eph_raw = pd.read_csv(args.eph_persons, sep=";", dtype=str, keep_default_na=False, low_memory=False)
    eph_scores = pd.read_parquet(args.eph_matched_person_scores)
    census_scores = pd.read_parquet(args.census_matched_person_scores)
    eph_support = pd.read_parquet(args.eph_support_scores)
    census_support = pd.read_parquet(args.census_support_scores)
    census_p1 = pd.read_parquet(args.census_p1)
    selection = pd.read_parquet(args.census_selection)
    department_region = pd.read_csv(args.department_region, dtype=str, keep_default_na=False)
    residuals = pd.read_parquet(args.fold_residuals)

    cba, cbt = regional_lines_from_telescope_b(b_hh)
    census_hh_lines, census_people = build_census_lines(
        census_p1, selection, department_region, cba, cbt,
        method_path=args.method,
    )
    eph_hh, eph_people, fold_mix = build_eph_validation(
        b_hh, eph_raw, eph_scores, eph_support, residuals, period=args.period
    )
    census_hh, census_support_people = build_census_matched(
        census_hh_lines, census_people, census_scores, census_support,
        residuals, fold_mix,
    )

    bridge, decomposition = build_bridge(eph_hh, census_hh, fold_mix)
    margin_summary, margin_bins = build_margin_diagnostics(eph_hh, census_hh, fold_mix)
    support_bins, support_hard, support_tail, cutpoints, tail_cut = support_quintile_stats(
        eph_people, census_support_people, census_hh, fold_mix
    )
    composition = composition_standardization(eph_people, support_bins, bridge, cutpoints)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    bridge.to_csv(output / "bridge.csv", index=False)
    decomposition.to_csv(output / "transport_decomposition.csv", index=False)
    margin_summary.to_csv(output / "margin_summary.csv", index=False)
    margin_bins.to_csv(output / "margin_bins.csv", index=False)
    support_bins.to_csv(output / "support_bins.csv", index=False)
    support_hard.to_csv(output / "support_hard.csv", index=False)
    support_tail.to_csv(output / "support_tail.csv", index=False)
    composition.to_csv(output / "composition_standardization.csv", index=False)

    summary = {
        "status": "RESEARCH_TRANSPORT_VALIDATION_NOT_OFFICIAL_INDEC_STATISTICS",
        "period": args.period,
        "c0": {
            "eph_households": int(len(eph_hh)),
            "eph_persons": int(eph_hh.member_count_records.sum()),
            "eph_person_weight_mass": float((eph_hh.PONDIH * eph_hh.member_count_records).sum()),
            "census_households": int(census_hh_lines.household_id.nunique()),
            "census_persons": int(len(census_people)),
            "fold_mix_by_eph_person_pondih_mass": {str(k): v for k, v in fold_mix.items()},
            "outer_models": sorted(fold_mix),
            "residual_policy": "reuse exact Telescope-B/Q7 G_-f unchanged",
            "monetary_reference": "same nominal Q3 welfare/lines; no scalar",
            "primary_estimand": "persons",
            "target_semantics": (
                "governed Census-derived target-year sample; department-level person mass "
                "updated by sampler design, within-department donor-frame composition assumed"
            ),
        },
        "transport_decomposition": decomposition.to_dict("records"),
        "support": {
            "target_person_score_quintile_cutpoints": cutpoints.tolist(),
            "weakest5_threshold": tail_cut,
            "support_score_semantics": "cross-fitted equal-prior target-domain probability; diagnostic only",
        },
        "composition_standardization": composition.to_dict("records"),
        "limitations": [
            "Census target is not observed 2024 household microdata",
            "no national target-year household analysis weight is authorized",
            "support probabilities are diagnostics, not production weights",
            "C4 standardizes only on support-score quintiles, not the full covariate vector",
            "residual heteroskedasticity documented by Telescope B is not repaired here",
            "aggregate uncertainty is not supplied",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    (output / "report.md").write_text(render_report(summary))
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Telescope C EPH-to-Census transport microscope")
    p.add_argument("--telescope-b-households", type=Path, required=True)
    p.add_argument("--eph-persons", type=Path, required=True)
    p.add_argument("--eph-matched-person-scores", type=Path, required=True)
    p.add_argument("--census-matched-person-scores", type=Path, required=True)
    p.add_argument("--eph-support-scores", type=Path, required=True)
    p.add_argument("--census-support-scores", type=Path, required=True)
    p.add_argument("--census-p1", type=Path, required=True)
    p.add_argument("--census-selection", type=Path, required=True)
    p.add_argument("--department-region", type=Path, required=True)
    p.add_argument("--fold-residuals", type=Path, required=True)
    p.add_argument("--period", default="2024-Q3")
    p.add_argument("--method", default=DEFAULT_METHOD)
    p.add_argument("--output", type=Path, required=True)
    return p


def main() -> None:
    args = parser().parse_args()
    summary = run(args)
    print(json.dumps({
        "status": summary["status"],
        "period": summary["period"],
        "eph_persons": summary["c0"]["eph_persons"],
        "census_persons": summary["c0"]["census_persons"],
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
