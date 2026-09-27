from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


STATE_LABELS = {
    0: "individual_nonresponse",
    1: "employed",
    2: "unemployed",
    3: "inactive_10_plus",
    4: "under_10",
}
VALID_STATES = frozenset(STATE_LABELS)
ACTIVE_STATES = frozenset({1, 2})
NON_ACTIVE_STATES = frozenset({3, 4})
CENSUS_IDENTITY_COLUMNS = (
    "sample_person_id",
    "frame_person_id",
    "sample_household_id",
    "frame_household_id",
    "frame_dwelling_id",
)


class LaborContractError(ValueError):
    """Raised when labor inputs violate an explicit scientific contract."""


def _numeric(series: pd.Series, name: str) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    if out.isna().any():
        raise LaborContractError(f"{name} contains non-numeric or missing values")
    return out


def canonicalize_eph(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the minimal canonical EPH labor frame without changing rows."""
    required = {"ESTADO", "PONDERA"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise LaborContractError(f"EPH labor frame missing columns: {missing}")

    out = frame.copy()
    out["ESTADO"] = _numeric(out["ESTADO"], "ESTADO").astype(int)
    out["PONDERA"] = _numeric(out["PONDERA"], "PONDERA").astype(float)
    unknown = sorted(set(out["ESTADO"]) - VALID_STATES)
    if unknown:
        raise LaborContractError(f"unsupported ESTADO values: {unknown}")
    if (~np.isfinite(out["PONDERA"])).any() or (out["PONDERA"] < 0).any():
        raise LaborContractError("PONDERA must be finite and non-negative")
    if float(out["PONDERA"].sum()) <= 0:
        raise LaborContractError("PONDERA total must be positive")
    return out


@dataclass(frozen=True)
class LaborSummary:
    row_count: int
    total_weight: float
    responded_weight: float
    state_weight: dict[int, float]
    state_rows: dict[int, int]
    activity_rate: float
    employment_rate: float
    unemployment_rate: float
    unweighted_activity_rate: float
    unweighted_employment_rate: float
    unweighted_unemployment_rate: float

    @property
    def accounting_gap(self) -> float:
        return self.total_weight - sum(self.state_weight.values())


def summarize_eph(frame: pd.DataFrame, *, require_pea: bool = True) -> LaborSummary:
    """Reconstruct headline A/E/U plus complete ESTADO accounting.

    PONDERA is the EPH general expansion factor. The headline denominator is the
    complete weighted person frame. ESTADO=0 is retained and reported rather than
    silently discarded so a non-zero individual-nonresponse mass is visible in QA.
    """
    work = canonicalize_eph(frame)
    state = work["ESTADO"]
    weight = work["PONDERA"]
    state_weight = {
        code: float(weight[state == code].sum()) for code in sorted(VALID_STATES)
    }
    state_rows = {code: int((state == code).sum()) for code in sorted(VALID_STATES)}
    total = float(weight.sum())
    responded = total - state_weight[0]
    employed = state_weight[1]
    unemployed = state_weight[2]
    pea = employed + unemployed
    if pea <= 0 and require_pea:
        raise LaborContractError("weighted economically active population must be positive")

    row_total = len(work)
    row_employed = state_rows[1]
    row_unemployed = state_rows[2]
    row_pea = row_employed + row_unemployed
    if row_total <= 0 or (row_pea <= 0 and require_pea):
        raise LaborContractError("sample must contain persons and economically active persons")

    return LaborSummary(
        row_count=row_total,
        total_weight=total,
        responded_weight=responded,
        state_weight=state_weight,
        state_rows=state_rows,
        activity_rate=pea / total,
        employment_rate=employed / total,
        unemployment_rate=(unemployed / pea if pea > 0 else math.nan),
        unweighted_activity_rate=row_pea / row_total,
        unweighted_employment_rate=row_employed / row_total,
        unweighted_unemployment_rate=(row_unemployed / row_pea if row_pea > 0 else math.nan),
    )


def summary_rate_rows(period: str, summary: LaborSummary) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for estimator, values in (
        (
            "pondera",
            {
                "activity": summary.activity_rate,
                "employment": summary.employment_rate,
                "unemployment": summary.unemployment_rate,
            },
        ),
        (
            "unweighted",
            {
                "activity": summary.unweighted_activity_rate,
                "employment": summary.unweighted_employment_rate,
                "unemployment": summary.unweighted_unemployment_rate,
            },
        ),
    ):
        for metric, value in values.items():
            rows.append(
                {
                    "period": period,
                    "estimator": estimator,
                    "metric": metric,
                    "rate": float(value),
                }
            )
    return rows


def summary_stock_rows(period: str, summary: LaborSummary) -> list[dict[str, object]]:
    rows = [
        {
            "period": period,
            "state": STATE_LABELS[code],
            "estado": code,
            "sample_rows": summary.state_rows[code],
            "pondera_mass": summary.state_weight[code],
        }
        for code in sorted(VALID_STATES)
    ]
    rows.extend(
        [
            {
                "period": period,
                "state": "population_total",
                "estado": -1,
                "sample_rows": summary.row_count,
                "pondera_mass": summary.total_weight,
            },
            {
                "period": period,
                "state": "responded_individual",
                "estado": -2,
                "sample_rows": summary.row_count - summary.state_rows[0],
                "pondera_mass": summary.responded_weight,
            },
            {
                "period": period,
                "state": "economically_active",
                "estado": -3,
                "sample_rows": summary.state_rows[1] + summary.state_rows[2],
                "pondera_mass": summary.state_weight[1] + summary.state_weight[2],
            },
            {
                "period": period,
                "state": "non_active",
                "estado": -4,
                "sample_rows": summary.state_rows[3] + summary.state_rows[4],
                "pondera_mass": summary.state_weight[3] + summary.state_weight[4],
            },
        ]
    )
    return rows


def benchmark_deltas(
    period: str,
    summary: LaborSummary,
    benchmark_row: pd.Series | dict[str, object],
) -> list[dict[str, object]]:
    official = {
        "activity": float(benchmark_row["activity_rate"]),
        "employment": float(benchmark_row["employment_rate"]),
        "unemployment": float(benchmark_row["unemployment_rate"]),
    }
    reconstructed = {
        "activity": summary.activity_rate,
        "employment": summary.employment_rate,
        "unemployment": summary.unemployment_rate,
    }
    return [
        {
            "period": period,
            "metric": metric,
            "reconstructed_rate": reconstructed[metric],
            "official_rate": official[metric],
            "delta_pp": 100.0 * (reconstructed[metric] - official[metric]),
        }
        for metric in ("activity", "employment", "unemployment")
    ]


def _age_group(series: pd.Series) -> pd.Series:
    age = pd.to_numeric(series, errors="coerce")
    bins = [-np.inf, 13, 29, 64, np.inf]
    labels = ["0-13", "14-29", "30-64", "65+"]
    out = pd.cut(age, bins=bins, labels=labels)
    return out.astype("string").fillna("unknown")


def add_microscope_dimensions(frame: pd.DataFrame) -> pd.DataFrame:
    """Add stable one-dimensional microscope fields when source columns exist."""
    out = frame.copy()
    if "CH06" in out:
        out["labor_age_group"] = _age_group(out["CH06"])
    elif "P03" in out:
        out["labor_age_group"] = _age_group(out["P03"])

    if "CH04" in out:
        sex = pd.to_numeric(out["CH04"], errors="coerce")
        out["labor_sex"] = sex.map({1: "male", 2: "female"}).fillna("unknown")
    elif "P02" in out:
        sex = pd.to_numeric(out["P02"], errors="coerce")
        out["labor_sex"] = sex.map({1: "male", 2: "female"}).fillna("unknown")

    if "AGLOMERADO" in out:
        aglo = pd.to_numeric(out["AGLOMERADO"], errors="coerce")
        out["labor_agglomerate"] = aglo.map(
            lambda x: f"{int(x):02d}" if pd.notna(x) else "unknown"
        )
    region_col = next((c for c in ("REGION", "Region", "region") if c in out), None)
    if region_col:
        out["labor_region"] = out[region_col].astype("string").fillna("unknown")
    return out


def microscope_rows(
    period: str,
    frame: pd.DataFrame,
    dimensions: Iterable[str] = (
        "labor_agglomerate",
        "labor_region",
        "labor_sex",
        "labor_age_group",
    ),
) -> list[dict[str, object]]:
    """Produce weighted and unweighted A/E/U by one dimension at a time."""
    work = add_microscope_dimensions(canonicalize_eph(frame))
    rows: list[dict[str, object]] = []
    for dimension in dimensions:
        if dimension not in work:
            continue
        for group_id, group in work.groupby(dimension, dropna=False, sort=True):
            summary = summarize_eph(group, require_pea=False)
            for rate_row in summary_rate_rows(period, summary):
                if not math.isfinite(float(rate_row["rate"])):
                    continue
                rows.append(
                    {
                        "period": period,
                        "dimension": dimension.removeprefix("labor_"),
                        "group_id": str(group_id),
                        "estimator": rate_row["estimator"],
                        "metric": rate_row["metric"],
                        "rate": rate_row["rate"],
                        "sample_rows": summary.row_count,
                        "pondera_mass": summary.total_weight,
                    }
                )
    return rows


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities.astype(float), 1e-9, 1.0 - 1e-9)
    return np.log(clipped / (1.0 - clipped))


def _expit(values: np.ndarray) -> np.ndarray:
    positive = values >= 0
    out = np.empty_like(values, dtype=float)
    out[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    out[~positive] = exp_values / (1.0 + exp_values)
    return out


def calibrate_logit_offset(
    probabilities: Iterable[float],
    target_mean: float,
    *,
    weights: Iterable[float] | None = None,
    tol: float = 1e-12,
    max_iter: int = 200,
) -> tuple[np.ndarray, float]:
    """Shift logits by one scalar so a (possibly weighted) mean matches target_mean."""
    p = np.asarray(list(probabilities), dtype=float)
    if p.size == 0 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise LaborContractError("probabilities must be finite and in [0, 1]")
    if not (0.0 < float(target_mean) < 1.0):
        raise LaborContractError("calibration target must be strictly between 0 and 1")
    if weights is None:
        w = np.ones_like(p, dtype=float)
    else:
        w = np.asarray(list(weights), dtype=float)
        if len(w) != len(p) or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
            raise LaborContractError("calibration weights must be finite, non-negative, and positive in total")
    logits = _logit(p)
    lo, hi = -40.0, 40.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        shifted = _expit(logits + mid)
        mean = float(np.average(shifted, weights=w))
        if abs(mean - target_mean) <= tol:
            return _expit(logits + mid), mid
        if mean < target_mean:
            lo = mid
        else:
            hi = mid
    shifted = _expit(logits + (lo + hi) / 2.0)
    if abs(float(np.average(shifted, weights=w)) - target_mean) > max(tol * 10, 1e-10):
        raise LaborContractError("logit-offset calibration did not converge")
    return shifted, (lo + hi) / 2.0


def validate_census_identity(frame: pd.DataFrame) -> dict[str, object]:
    """Validate all Census entity identities present on a person-level surface."""
    if "sample_person_id" not in frame:
        raise LaborContractError("labor probability frame missing columns: ['sample_person_id']")
    if frame["sample_person_id"].astype(str).duplicated().any():
        raise LaborContractError("sample_person_id must be unique")

    present = [column for column in CENSUS_IDENTITY_COLUMNS if column in frame.columns]
    if "frame_person_id" in frame and frame["frame_person_id"].astype(str).duplicated().any():
        raise LaborContractError("frame_person_id must be unique")

    relationships: dict[str, object] = {}
    pairs = (
        ("sample_person_id", "sample_household_id", "person_to_sample_household"),
        ("frame_person_id", "frame_household_id", "frame_person_to_household"),
        ("sample_household_id", "frame_household_id", "sample_household_to_frame_household"),
        ("frame_household_id", "frame_dwelling_id", "frame_household_to_dwelling"),
    )
    for child, parent, label in pairs:
        if child not in frame or parent not in frame:
            continue
        pair = frame[[child, parent]].astype("string").drop_duplicates()
        if pair[[child, parent]].isna().any().any():
            raise LaborContractError(f"{label} contains missing identity values")
        parent_counts = pair.groupby(child, dropna=False)[parent].nunique(dropna=False)
        violating = int((parent_counts != 1).sum())
        if violating:
            raise LaborContractError(
                f"{label} must be many-to-one: violating_children={violating}"
            )
        relationships[label] = {
            "child": child,
            "parent": parent,
            "status": "validated",
        }
    return {
        "identity_columns": present,
        "person_key": ["sample_person_id"],
        "relationships": relationships,
    }


def validate_probability_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "sample_person_id",
        "p_active_raw",
        "p_unemployed_given_active_raw",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise LaborContractError(f"labor probability frame missing columns: {missing}")
    validate_census_identity(frame)
    out = frame.copy()
    for column in ("p_active_raw", "p_unemployed_given_active_raw"):
        values = pd.to_numeric(out[column], errors="coerce")
        if values.isna().any() or ((values < 0) | (values > 1)).any():
            raise LaborContractError(f"{column} must be in [0, 1]")
        out[column] = values.astype(float)
    return out


def calibrate_census_domains(
    probabilities: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    domain_col: str = "calibration_domain_id",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calibrate Census labor probabilities to official A/U targets by domain.

    The target-year Census sample is intentionally treated as self-weighting for
    analysis here. samplerCensoARG's design_inverse_probability_weight is not
    consumed by this function.
    """
    work = validate_probability_frame(probabilities)
    if domain_col not in work:
        raise LaborContractError(f"probability frame missing {domain_col}")
    required_targets = {domain_col, "activity_rate", "unemployment_rate"}
    missing = sorted(required_targets - set(targets.columns))
    if missing:
        raise LaborContractError(f"labor targets missing columns: {missing}")
    if targets[domain_col].astype(str).duplicated().any():
        raise LaborContractError("labor target domains must be unique")

    target_map = targets.set_index(targets[domain_col].astype(str), drop=False)
    parts: list[pd.DataFrame] = []
    qa_rows: list[dict[str, object]] = []
    for raw_domain, group in work.groupby(domain_col, dropna=False, sort=False):
        group = group.copy()
        if pd.isna(raw_domain) or str(raw_domain) in {"", "None", "<NA>", "nan"}:
            group["p_active"] = group["p_active_raw"]
            group["p_unemployed_given_active"] = group["p_unemployed_given_active_raw"]
            status = "MODELLED_UNBENCHMARKED"
            alpha = beta = math.nan
            target_activity = target_unemployment = math.nan
            target_employment = math.nan
        else:
            domain = str(raw_domain)
            if domain not in target_map.index:
                raise LaborContractError(f"missing official labor target for domain {domain}")
            target = target_map.loc[domain]
            target_activity = float(target["activity_rate"])
            target_unemployment = float(target["unemployment_rate"])
            target_employment = (
                float(target["employment_rate"])
                if "employment_rate" in targets and pd.notna(target.get("employment_rate"))
                else target_activity * (1.0 - target_unemployment)
            )
            calibrated_active, alpha = calibrate_logit_offset(
                group["p_active_raw"].to_numpy(), target_activity
            )
            calibrated_u, beta = calibrate_logit_offset(
                group["p_unemployed_given_active_raw"].to_numpy(),
                target_unemployment,
                weights=calibrated_active,
            )
            group["p_active"] = calibrated_active
            group["p_unemployed_given_active"] = calibrated_u
            status = "MODELLED_AND_CALIBRATED"

        group["p_unemployed"] = (
            group["p_active"] * group["p_unemployed_given_active"]
        )
        group["p_employed"] = group["p_active"] - group["p_unemployed"]
        group["p_inactive"] = 1.0 - group["p_active"]
        group["calibration_status"] = status
        parts.append(group)

        activity = float(group["p_active"].mean())
        unemployed = float(group["p_unemployed"].sum())
        active_mass = float(group["p_active"].sum())
        unemployment = unemployed / active_mass if active_mass > 0 else math.nan
        employment = float(group["p_employed"].mean())
        qa_rows.append(
            {
                domain_col: None if pd.isna(raw_domain) else str(raw_domain),
                "status": status,
                "rows": len(group),
                "alpha_activity_logit_shift": alpha,
                "beta_unemployment_logit_shift": beta,
                "activity_rate": activity,
                "unemployment_rate": unemployment,
                "employment_rate": employment,
                "target_activity_rate": target_activity,
                "target_unemployment_rate": target_unemployment,
                "target_employment_rate": target_employment,
                "activity_delta_pp": (
                    100 * (activity - target_activity)
                    if math.isfinite(target_activity) else math.nan
                ),
                "unemployment_delta_pp": (
                    100 * (unemployment - target_unemployment)
                    if math.isfinite(target_unemployment) else math.nan
                ),
                "employment_delta_pp": (
                    100 * (employment - target_employment)
                    if math.isfinite(target_employment) else math.nan
                ),
            }
        )

    out = pd.concat(parts, ignore_index=True)
    probability_sum = out[["p_employed", "p_unemployed", "p_inactive"]].sum(axis=1)
    if not np.allclose(probability_sum, 1.0, atol=1e-12, rtol=0):
        raise LaborContractError("calibrated labor probabilities do not sum to one")
    return out, pd.DataFrame(qa_rows)


def calibration_targets_from_microscope(
    microscope: pd.DataFrame,
    period: str,
    *,
    dimension: str = "agglomerate",
    estimator: str = "pondera",
    domain_col: str = "calibration_domain_id",
) -> pd.DataFrame:
    """Promote governed EPH microscope A/E/U rows into precise L3 domain targets."""
    required = {"period", "dimension", "group_id", "estimator", "metric", "rate"}
    missing = sorted(required - set(microscope.columns))
    if missing:
        raise LaborContractError(f"labor microscope missing columns: {missing}")
    subset = microscope[
        (microscope["period"].astype(str) == str(period))
        & (microscope["dimension"].astype(str) == dimension)
        & (microscope["estimator"].astype(str) == estimator)
        & microscope["metric"].isin(["activity", "employment", "unemployment"])
    ].copy()
    if subset.empty:
        raise LaborContractError(
            f"no {dimension}/{estimator} labor microscope rows for {period}"
        )
    if subset.duplicated(["group_id", "metric"]).any():
        raise LaborContractError("labor microscope has duplicate domain/metric rows")
    pivot = subset.pivot(index="group_id", columns="metric", values="rate")
    needed = {"activity", "employment", "unemployment"}
    if set(pivot.columns) != needed or pivot[list(sorted(needed))].isna().any().any():
        raise LaborContractError(
            "every calibration domain must expose activity/employment/unemployment"
        )
    out = pivot.reset_index().rename(
        columns={
            "group_id": domain_col,
            "activity": "activity_rate",
            "employment": "employment_rate",
            "unemployment": "unemployment_rate",
        }
    )
    out.insert(0, "period", str(period))
    out[domain_col] = out[domain_col].astype(str)
    return out.sort_values(domain_col, kind="stable").reset_index(drop=True)
