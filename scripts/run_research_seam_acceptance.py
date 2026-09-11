#!/usr/bin/env python3
"""Local-only acceptance runner for the first real predictive-welfare poverty seam.

This script intentionally depends on local immutable artifacts. It does not fetch data,
retrain models, or publish official statistics. It proves the research seam by:

1. validating exact sampler/semantic/Q8 identities;
2. validating direct EPH poverty against the frozen poverty method and Q3 baskets;
3. integrating the governed predictive welfare distribution over household-specific
   CBA/CBT lines for EPH and Census;
4. aggregating unit-weight household/person expected FGT0/1/2.

Large outputs remain local; only small evidence summaries are intended for Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from poverty_pipeline.predictive_measurement import (
    EmpiricalResidualWelfare,
    PredictiveHouseholdWelfare,
    expected_fgt_contribution,
)
from poverty_pipeline.science import load_poverty_method


REGION_MAP = {
    1: "gran_buenos_aires",
    40: "noroeste",
    41: "noreste",
    42: "cuyo",
    43: "pampeana",
    44: "patagonia",
}
SEX_MAP = {1: "male", 2: "female"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_baskets(path: Path, q3_date: str = "2024-08-15") -> dict[str, tuple[float, float]]:
    df = pd.read_csv(path)
    date_col = next((c for c in ["date", "Fecha", "period", "Q"] if c in df.columns), None)
    if date_col is None:
        date_col = df.columns[0]
    x = df[df[date_col].astype(str) == q3_date].copy()
    if len(x) != 6:
        raise RuntimeError(f"expected six 2024-Q3 basket rows, got {len(x)}")
    region_col = next(c for c in x.columns if c.lower() in {"region", "region_id"})
    cba_col = next(c for c in x.columns if "cba" in c.lower())
    cbt_col = next(c for c in x.columns if "cbt" in c.lower())
    out = {str(r[region_col]).strip().lower().replace(" ", "_"): (float(r[cba_col]), float(r[cbt_col])) for _, r in x.iterrows()}
    aliases = {"patagónica": "patagonia", "patagonica": "patagonia", "gran_buenos_aires": "gran_buenos_aires"}
    out = {aliases.get(k, k): v for k, v in out.items()}
    required = set(REGION_MAP.values())
    if set(out) != required:
        raise RuntimeError(f"basket regions mismatch: have={sorted(out)} required={sorted(required)}")
    return out


def household_lines(persons: pd.DataFrame, household_region: pd.Series, baskets, method):
    persons = persons.copy()
    persons["ae"] = [method.adult_equivalence(sex=s, age=int(a)) for s, a in zip(persons.sex, persons.age)]
    ae = persons.groupby("household_id").ae.sum()
    region = household_region.reindex(ae.index)
    if region.isna().any():
        raise RuntimeError(f"missing region for {int(region.isna().sum())} households")
    cba = pd.Series({h: baskets[region[h]][0] * ae[h] for h in ae.index})
    cbt = pd.Series({h: baskets[region[h]][1] * ae[h] for h in ae.index})
    return pd.DataFrame({"adult_equivalents": ae, "region": region, "household_cba": cba, "household_cbt": cbt})


def fgt_point(welfare: pd.Series, line: pd.Series, alpha: int) -> pd.Series:
    w, z = welfare.align(line, join="inner")
    if alpha == 0:
        return (w <= z).astype(float)
    return ((z - w).clip(lower=0) / z) ** alpha


def predictive_contributions(location: pd.Series, lines: pd.DataFrame, residuals: np.ndarray) -> pd.DataFrame:
    dist = EmpiricalResidualWelfare(tuple(float(x) for x in np.sort(residuals)))
    rows = []
    for h, loc in location.items():
        cba = float(lines.at[h, "household_cba"])
        cbt = float(lines.at[h, "household_cbt"])
        rows.append({
            "household_id": h,
            "indigence_fgt0": expected_fgt_contribution(float(loc), cba, 0, dist),
            "indigence_fgt1": expected_fgt_contribution(float(loc), cba, 1, dist),
            "indigence_fgt2": expected_fgt_contribution(float(loc), cba, 2, dist),
            "poverty_fgt0": expected_fgt_contribution(float(loc), cbt, 0, dist),
            "poverty_fgt1": expected_fgt_contribution(float(loc), cbt, 1, dist),
            "poverty_fgt2": expected_fgt_contribution(float(loc), cbt, 2, dist),
        })
    return pd.DataFrame(rows).set_index("household_id")


def summary(frame: pd.DataFrame) -> dict[str, float]:
    keys = [f"{c}_fgt{a}" for c in ("indigence", "poverty") for a in range(3)]
    return {k: float(frame[k].mean()) for k in keys}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sampler", type=Path, required=True)
    ap.add_argument("--semantic", type=Path, required=True)
    ap.add_argument("--q7", type=Path, required=True)
    ap.add_argument("--q8", type=Path, required=True)
    ap.add_argument("--eph", type=Path, required=True)
    ap.add_argument("--baskets", type=Path, required=True)
    ap.add_argument("--department-region", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--monetary-scalar", type=float, default=0.011493967206201482)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    method = load_poverty_method("configs/poverty_methods/indec-line-poverty-2016-v1.json")
    baskets = load_baskets(args.baskets)
    scalar = args.monetary_scalar

    # --- Census identities/frame ---
    sel = pd.read_parquet(args.sampler / "selection.parquet")
    pm = pd.read_parquet(args.sampler / "person_membership.parquet")
    persona = pd.read_parquet(args.sampler / "persona.parquet")
    sem = pd.read_parquet(args.semantic / "census_p1.parquet")
    q8p = pd.read_parquet(args.q8 / "person_predictions.parquet")
    q8h = pd.read_parquet(args.q8 / "household_predictions.parquet")
    if len(pm) != 469172 or len(sel) != 141863:
        raise RuntimeError("unexpected sampler row counts")
    if set(sem.row_id.astype(str)) != set(pm.sample_person_id.astype(str)):
        raise RuntimeError("semantic/sampler person identity mismatch")
    if set(q8h.household_id.astype(str)) != set(sel.sample_household_id.astype(str)):
        raise RuntimeError("Q8/sampler household identity mismatch")

    p = pm.merge(persona[["frame_person_id", "P02", "P03"]], on="frame_person_id", validate="one_to_one")
    p["person_id"] = p.sample_person_id.astype(str)
    p["household_id"] = p.sample_household_id.astype(str)
    p["sex"] = pd.to_numeric(p.P02, errors="raise").map(SEX_MAP)
    p["age"] = pd.to_numeric(p.P03, errors="raise").astype(int)
    if p.sex.isna().any():
        raise RuntimeError("unknown Census sex code")
    hh_geo = sel.set_index("sample_household_id").department_id.astype(str)
    bind = pd.read_csv(args.department_region, dtype={"DPTO": str})
    bind["department_id"] = bind.DPTO.astype(str)
    bind["region"] = bind.Region.astype(str).str.lower().str.replace(" ", "_", regex=False).replace({"patagónica": "patagonia", "patagonica": "patagonia"})
    region_by_dep = bind.drop_duplicates("department_id").set_index("department_id").region
    census_region = hh_geo.map(region_by_dep)
    if census_region.isna().any():
        raise RuntimeError(f"unmapped Census departments: {sorted(hh_geo[census_region.isna()].unique())[:20]}")
    census_lines = household_lines(p[["household_id", "sex", "age"]], census_region, baskets, method)

    # residual ECDF is rebuilt from exact EPH/Q8 deployment contract if no promoted artifact exists yet
    # Q8 uses 5-fold OOF P1-R household residuals on the 12,568 complete cohort.
    ind = pd.read_csv(args.eph / "individual/usu_individual_t324.txt", sep=";", dtype=str, keep_default_na=False)
    ind["hh"] = ind.CODUSU + "\x1f" + ind.NRO_HOGAR
    ind["y"] = pd.to_numeric(ind.P47T, errors="coerce")
    po = pd.read_json(args.q7.parent.parent / "q2_p1r" / "person_oof.jsonl", lines=True)
    ind["row_id"] = ind.CODUSU + ":" + ind.NRO_HOGAR + ":" + ind.COMPONENTE
    ep = ind.merge(po[["row_id", "pred"]], on="row_id", how="inner", validate="one_to_one")
    complete = pd.read_json(Path("/home/matias/Downloads/real-eph-2024q3-science-evidence/encuestador-runs/real_eph_2024q3_direct_hurdle_gamma_v1-7f010f6cb22b4d9c/household_oof.jsonl"), lines=True)
    complete_hh = {x.split("\x1f")[0] + "\x1f" + x.split("\x1f")[1] for x in complete.loc[complete.observed_household_income.notna(), "household_observation_id"]}
    eg = ep[ep.hh.isin(complete_hh)].groupby("hh").agg(y=("y", "sum"), pred=("pred", "sum"))
    residuals = (eg.y - eg.pred).to_numpy(float) * scalar

    # --- EPH direct and predictive validation ---
    eh = pd.read_csv(args.eph / "household/usu_hogar_t324.txt", sep=";", dtype=str, keep_default_na=False)
    eh["hh"] = eh.CODUSU + "\x1f" + eh.NRO_HOGAR
    eph_region = pd.to_numeric(eh.REGION, errors="raise").map(REGION_MAP)
    eph_region.index = eh.hh
    ei = ind[ind.hh.isin(complete_hh) & ind.y.notna() & (ind.y >= 0)].copy()
    ei["household_id"] = ei.hh
    ei["sex"] = pd.to_numeric(ei.CH04, errors="raise").map(SEX_MAP)
    ei["age"] = pd.to_numeric(ei.CH06, errors="raise").astype(int)
    eph_lines = household_lines(ei[["household_id", "sex", "age"]], eph_region, baskets, method)
    observed = ei.groupby("household_id").y.sum() * scalar
    point = eg.pred * scalar
    direct = pd.DataFrame(index=observed.index)
    for concept, col in [("indigence", "household_cba"), ("poverty", "household_cbt")]:
        for a in range(3):
            direct[f"{concept}_fgt{a}"] = fgt_point(observed, eph_lines[col], a)
    pred = predictive_contributions(point, eph_lines, residuals)

    # --- Census predictive poverty ---
    census_location = q8h.set_index("household_id").predicted_household_income.astype(float) * scalar
    census_pred = predictive_contributions(census_location, census_lines, residuals)

    # Person-universe estimates are member-count weighted averages of household contributions.
    census_members = p.groupby("household_id").size().rename("members")
    def person_summary(frame):
        z = frame.join(census_members, how="inner")
        keys = [f"{c}_fgt{a}" for c in ("indigence", "poverty") for a in range(3)]
        return {k: float(np.average(z[k], weights=z.members)) for k in keys}

    evidence = {
        "status": "RESEARCH_COMMISSIONING_NOT_OFFICIAL_STATISTICS",
        "monetary_scalar": scalar,
        "counts": {"census_persons": len(p), "census_households": len(census_pred), "eph_complete_households": len(direct)},
        "eph_direct": summary(direct),
        "eph_predictive": summary(pred),
        "eph_delta_predictive_minus_direct": {k: summary(pred)[k] - summary(direct)[k] for k in summary(direct)},
        "census_households": summary(census_pred),
        "census_persons": person_summary(census_pred),
        "parents": {
            "sampler_manifest_sha256": sha256(args.sampler / "manifest.json"),
            "semantic_manifest_sha256": sha256(args.semantic / "manifest.json"),
            "q8_household_predictions_sha256": sha256(args.q8 / "household_predictions.parquet"),
            "basket_file_sha256": sha256(args.baskets),
            "department_region_sha256": sha256(args.department_region),
        },
        "limitations": [
            "collective/private dwelling separation deferred",
            "unit-weight research estimation",
            "aggregate uncertainty not supplied",
            "Q8 transport caveats remain active",
        ],
    }
    (args.output / "acceptance_summary.json").write_text(json.dumps(evidence, indent=2, sort_keys=True))
    direct.to_parquet(args.output / "eph_direct_household_fgt.parquet")
    pred.to_parquet(args.output / "eph_predictive_household_fgt.parquet")
    census_pred.to_parquet(args.output / "census_predictive_household_fgt.parquet")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
