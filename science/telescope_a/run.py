#!/usr/bin/env python3
"""Telescope A T0-T2: direct observed-EPH poverty microscope."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from poverty_pipeline.estimation_v2 import (
    EstimationContext, EstimationDesign, HouseholdDomain, HouseholdWeight, estimate_poverty,
)
from poverty_pipeline.science import (
    HouseholdPovertyLines, HouseholdWelfare, PersonMember, load_poverty_method, measure_poverty,
)

REGION_MAP = {1: "gran_buenos_aires", 40: "noroeste", 41: "noreste", 42: "cuyo", 43: "pampeana", 44: "patagonia"}
REGIONS = tuple(sorted(REGION_MAP.values()))
SEX_MAP = {1: "male", 2: "female"}
HH_COLS = ("CODUSU", "NRO_HOGAR", "ANO4", "TRIMESTRE", "REGION", "AGLOMERADO", "IX_TOT", "ITF", "IPCF", "PONDIH")
P_COLS = ("CODUSU", "NRO_HOGAR", "COMPONENTE", "ANO4", "TRIMESTRE", "CH04", "CH06", "P47T")
DEFAULT_METHOD = "configs/poverty_methods/indec-line-poverty-2016-v1.json"


class TelescopeAError(ValueError):
    pass


def require(df, cols, label):
    missing = sorted(set(cols) - set(df.columns))
    if missing:
        raise TelescopeAError(f"{label} missing columns: {missing}")


def period_parts(period):
    try:
        y, q = period.upper().split("-Q"); y, q = int(y), int(q)
    except (ValueError, AttributeError) as exc:
        raise TelescopeAError("period must be YYYY-Q1..Q4") from exc
    if q not in (1, 2, 3, 4):
        raise TelescopeAError("period must be YYYY-Q1..Q4")
    m0 = 1 + 3 * (q - 1)
    return y, q, tuple(pd.Timestamp(y, m, 1) for m in range(m0, m0 + 3))


def _household_ids(df):
    return df.ANO4.astype(str).str.strip() + ":" + df.TRIMESTRE.astype(str).str.strip() + ":" + df.CODUSU.astype(str).str.strip() + ":" + df.NRO_HOGAR.astype(str).str.strip()


def _person_ids(df):
    return _household_ids(df) + ":" + df.COMPONENTE.astype(str).str.strip()


def quarter_basket(df, period, label):
    require(df, REGIONS, label)
    date_col = next((c for c in ("indice_tiempo", "period", "date", "Fecha") if c in df), None)
    if date_col is None:
        raise TelescopeAError(f"{label} needs a date column")
    _, _, months = period_parts(period)
    dates = pd.to_datetime(df[date_col], errors="coerce").dt.to_period("M").dt.to_timestamp()
    if dates.isna().any():
        raise TelescopeAError(f"{label} has bad dates")
    selected = df.loc[dates.isin(months)].copy(); selected["_month"] = dates[dates.isin(months)].to_numpy()
    counts = selected._month.value_counts()
    if set(counts.index) != set(months) or not (counts == 1).all():
        raise TelescopeAError(f"{label} must contain each requested month exactly once")
    out = {}
    for region in REGIONS:
        values = pd.to_numeric(selected[region], errors="coerce")
        if values.isna().any() or (values <= 0).any():
            raise TelescopeAError(f"{label} has invalid {region} values")
        out[region] = float(values.mean())
    return out


def _assert_period(df, year, quarter, label):
    y = pd.to_numeric(df.ANO4, errors="coerce"); q = pd.to_numeric(df.TRIMESTRE, errors="coerce")
    observed = set(zip(y.dropna().astype(int), q.dropna().astype(int)))
    if y.isna().any() or q.isna().any() or observed != {(year, quarter)}:
        raise TelescopeAError(f"{label} period mismatch: {sorted(observed)}")


def _accounting(m):
    complete = m[m.P47T_complete]
    d = complete.itf_minus_sum_p47t.dropna().astype(float)
    i = m.ipcf_delta.dropna().astype(float)
    return {
        "p47t_complete_households": int(len(complete)),
        "p47t_complete_share_retained": float(len(complete) / len(m)),
        "itf_equals_sum_p47t_exact_share_complete": float((d == 0).mean()) if len(d) else None,
        "itf_minus_sum_p47t": None if not len(d) else {"mean": float(d.mean()), "median": float(d.median()), "p01": float(d.quantile(.01)), "p99": float(d.quantile(.99)), "max_abs": float(d.abs().max())},
        "ipcf_minus_itf_per_member": None if not len(i) else {"exact_zero_share": float((i == 0).mean()), "mean": float(i.mean()), "median": float(i.median()), "max_abs": float(i.abs().max())},
    }


def build_telescope(hh_raw, p_raw, cba_raw, cbt_raw, *, period="2024-Q3", method_path=DEFAULT_METHOD):
    """Return (household microscope, T2 summary) for exactly one EPH quarter."""
    year, quarter, _ = period_parts(period)
    hh, p = hh_raw.copy(), p_raw.copy()
    require(hh, HH_COLS, "households"); require(p, P_COLS, "persons")
    for df, cols in ((hh, HH_COLS), (p, P_COLS)):
        for c in cols: df[c] = df[c].astype(str).str.strip()
    _assert_period(hh, year, quarter, "households"); _assert_period(p, year, quarter, "persons")

    hh["household_id"] = _household_ids(hh); p["household_id"] = _household_ids(p); p["person_id"] = _person_ids(p)
    if hh.household_id.duplicated().any(): raise TelescopeAError("duplicate household identity")
    if p.person_id.duplicated().any(): raise TelescopeAError("duplicate person identity")
    hset, pset = set(hh.household_id), set(p.household_id)
    if pset - hset: raise TelescopeAError(f"persons reference absent households: {sorted(pset-hset)[:20]}")
    if hset - pset: raise TelescopeAError(f"households have no persons: {sorted(hset-pset)[:20]}")

    counts = p.groupby("household_id").size().rename("member_count_records")
    hh = hh.merge(counts, on="household_id", validate="one_to_one")
    hh["IX_TOT"] = pd.to_numeric(hh.IX_TOT, errors="coerce")
    if hh.IX_TOT.isna().any(): raise TelescopeAError("invalid IX_TOT")
    hh["membership_match"] = hh.IX_TOT == hh.member_count_records
    if not hh.membership_match.all(): raise TelescopeAError("IX_TOT/person membership mismatch")

    hh["basket_region"] = pd.to_numeric(hh.REGION, errors="coerce").map(REGION_MAP)
    if hh.basket_region.isna().any(): raise TelescopeAError(f"unknown EPH REGION codes: {sorted(hh.loc[hh.basket_region.isna(),'REGION'].unique())}")
    hh["ITF"] = pd.to_numeric(hh.ITF, errors="coerce"); hh["ITF_valid"] = hh.ITF.notna() & (hh.ITF >= 0)
    hh["IPCF"] = pd.to_numeric(hh.IPCF, errors="coerce").where(lambda x: x >= 0)
    hh["PONDIH"] = pd.to_numeric(hh.PONDIH, errors="coerce")

    p["P47T_num"] = pd.to_numeric(p.P47T, errors="coerce"); p["P47T_valid"] = p.P47T_num.notna() & (p.P47T_num >= 0)
    complete = p.groupby("household_id").P47T_valid.all().rename("P47T_complete")
    sums = p[p.P47T_valid].groupby("household_id").P47T_num.sum()
    hh = hh.merge(complete, on="household_id", validate="one_to_one"); hh["sum_P47T"] = hh.household_id.map(sums)
    hh.loc[~hh.P47T_complete, "sum_P47T"] = np.nan

    raw_weight = hh.PONDIH.where(np.isfinite(hh.PONDIH) & (hh.PONDIH > 0)); raw_weight_mass = float(raw_weight.sum())
    keep = hh[hh.ITF_valid].copy()
    if keep.empty: raise TelescopeAError("no valid nonnegative ITF households")
    if keep.PONDIH.isna().any() or (~np.isfinite(keep.PONDIH)).any() or (keep.PONDIH <= 0).any(): raise TelescopeAError("retained PONDIH must be finite and positive")

    cba, cbt = quarter_basket(cba_raw, period, "CBA"), quarter_basket(cbt_raw, period, "CBT")
    if any(cba[r] > cbt[r] for r in REGIONS): raise TelescopeAError("CBA exceeds CBT")

    selected = p[p.household_id.isin(set(keep.household_id))].copy()
    selected["sex"] = pd.to_numeric(selected.CH04, errors="coerce").map(SEX_MAP)
    age = pd.to_numeric(selected.CH06, errors="coerce")
    if selected.sex.isna().any() or age.isna().any() or (age < 0).any() or ((age % 1) != 0).any(): raise TelescopeAError("invalid sex/age in retained households")
    selected["age"] = age.astype(int)

    method = load_poverty_method(method_path)
    people = tuple(PersonMember(r.person_id, r.household_id, r.sex, int(r.age)) for r in selected.itertuples())
    welfare = tuple(HouseholdWelfare(r.household_id, float(r.ITF)) for r in keep.itertuples())
    lines = tuple(HouseholdPovertyLines(r.household_id, cba[r.basket_region], cbt[r.basket_region]) for r in keep.itertuples())
    measurement = measure_poverty(people, welfare, lines, method)

    measured = pd.DataFrame(asdict(r) for r in measurement.households)
    cols = ["household_id","CODUSU","NRO_HOGAR","REGION","AGLOMERADO","basket_region","member_count_records","IX_TOT","membership_match","ITF","IPCF","sum_P47T","ITF_valid","P47T_complete","PONDIH"]
    m = keep[cols].merge(measured, on="household_id", validate="one_to_one")
    m["period"] = period; m["itf_minus_sum_p47t"] = m.ITF - m.sum_P47T; m["ipcf_reconstructed"] = m.ITF / m.member_count_records; m["ipcf_delta"] = m.IPCF - m.ipcf_reconstructed
    m["cba_per_ae"] = m.basket_region.map(cba); m["cbt_per_ae"] = m.basket_region.map(cbt)
    m["poor_non_indigent"] = m.poor & ~m.indigent; m["nonpoor"] = ~m.poor

    region = dict(zip(keep.household_id, keep.basket_region)); weight = dict(zip(keep.household_id, keep.PONDIH.astype(float)))
    ids = sorted(region)
    est = estimate_poverty(
        measurement,
        tuple(HouseholdDomain(h, "eph_region", region[h]) for h in ids),
        EstimationDesign(f"eph-pondih-{period.lower()}", "EPH PONDIH household-income nonresponse-adjusted expansion factor", tuple(HouseholdWeight(h, weight[h]) for h in ids)),
        EstimationContext(f"telescope-a-{period.lower()}-observed-eph", period, f"EPH-{period}"),
    )
    estimates = [asdict(r) for r in est.estimates]
    national = [r for r in estimates if r["geography_level"] == "national"]
    hden = float(m.PONDIH.sum()); pden = float((m.PONDIH * m.member_count_records).sum())
    getden = lambda u: next(float(r["weighted_denominator"]) for r in national if r["universe"] == u and r["concept"] == "poverty" and r["estimand"] == "fgt0")
    if not math.isclose(hden, getden("households")) or not math.isclose(pden, getden("persons")): raise TelescopeAError("PONDIH denominators do not reconcile")

    ordered = ["period","household_id","CODUSU","NRO_HOGAR","REGION","AGLOMERADO","basket_region","member_count_records","IX_TOT","membership_match","adult_equivalents","ITF","IPCF","sum_P47T","ITF_valid","P47T_complete","itf_minus_sum_p47t","ipcf_reconstructed","ipcf_delta","PONDIH","cba_per_ae","cbt_per_ae","household_cba","household_cbt","indigent","poor","poor_non_indigent","nonpoor","indigence_fgt0","indigence_fgt1","indigence_fgt2","poverty_fgt0","poverty_fgt1","poverty_fgt2","indigence_monetary_shortfall","poverty_monetary_shortfall"]
    m = m[ordered].sort_values("household_id").reset_index(drop=True)
    summary = {
        "status": "RESEARCH_VALIDATION_NOT_OFFICIAL_INDEC_STATISTICS", "period": period, "method_release_id": method.release_id,
        "basket_policy": "three_month_arithmetic_mean_of_explicit_nominal_regional_sources",
        "source_retention": {"raw_households": int(len(hh)), "raw_persons": int(len(p)), "retained_valid_itf_households": int(len(m)), "retained_persons": int(len(selected)), "excluded_invalid_itf_households": int((~hh.ITF_valid).sum()), "raw_positive_pondih_mass": raw_weight_mass, "retained_pondih_mass": hden},
        "accounting": _accounting(m),
        "denominator_reconciliation": {"expected_household_sum_pondih": hden, "estimator_household_denominator": getden("households"), "expected_person_sum_pondih_times_members": pden, "estimator_person_denominator": getden("persons"), "status": "passed"},
        "national_estimates": national, "regional_estimates": [r for r in estimates if r["geography_level"] == "eph_region"],
        "limitations": ["quarter-mean basket timing is a research approximation", "aggregate uncertainty is not supplied", "P47T is diagnostic only"],
    }
    return m, summary


def render_report(s):
    n = {(r["universe"],r["concept"],r["estimand"]): r["estimate"] for r in s["national_estimates"]}
    r = s["source_retention"]
    return f"""# Telescope A — {s['period']}\n\n> Research validation only; not official INDEC statistics.\n\n## Cohort\n- raw households: {r['raw_households']}\n- retained valid-ITF households: {r['retained_valid_itf_households']}\n- raw persons: {r['raw_persons']}\n- retained persons: {r['retained_persons']}\n\n## National weighted incidence\n| Universe | Indigence | Poverty |\n|---|---:|---:|\n| households | {100*n[('households','indigence','fgt0')]:.3f}% | {100*n[('households','poverty','fgt0')]:.3f}% |\n| persons | {100*n[('persons','indigence','fgt0')]:.3f}% | {100*n[('persons','poverty','fgt0')]:.3f}% |\n\nT2 denominators reconcile to `sum(PONDIH)` and `sum(PONDIH * member_count)`. See `summary.json` for accounting diagnostics and regional estimates.\n"""


def main():
    ap = argparse.ArgumentParser(description="Telescope A T0-T2 observed EPH poverty microscope")
    ap.add_argument("--eph-households", type=Path, required=True); ap.add_argument("--eph-persons", type=Path, required=True)
    ap.add_argument("--cba", type=Path, required=True); ap.add_argument("--cbt", type=Path, required=True)
    ap.add_argument("--period", default="2024-Q3"); ap.add_argument("--method", type=Path, default=Path(DEFAULT_METHOD)); ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    hh = pd.read_csv(a.eph_households, sep=";", dtype=str, keep_default_na=False, low_memory=False); p = pd.read_csv(a.eph_persons, sep=";", dtype=str, keep_default_na=False, low_memory=False)
    cba = pd.read_csv(a.cba, dtype=str, keep_default_na=False); cbt = pd.read_csv(a.cbt, dtype=str, keep_default_na=False)
    microscope, summary = build_telescope(hh, p, cba, cbt, period=a.period, method_path=a.method)
    a.output.mkdir(parents=True, exist_ok=True); microscope.to_parquet(a.output / "households.parquet", index=False)
    (a.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)); (a.output / "report.md").write_text(render_report(summary))
    print(json.dumps({"status": summary["status"], "period": a.period, "retained_households": len(microscope), "output": str(a.output)}, indent=2))


if __name__ == "__main__": main()
