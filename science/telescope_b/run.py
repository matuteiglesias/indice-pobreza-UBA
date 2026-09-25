#!/usr/bin/env python3
"""Telescope B: same-household observed -> OOF point -> nested predictive bridge."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

STATES = ("indigent", "poor_non_indigent", "nonpoor")
A_REQUIRED = ("household_id","member_count_records","ITF","sum_P47T","P47T_complete","PONDIH","household_cba","household_cbt")
P_REQUIRED = ("CODUSU","NRO_HOGAR","COMPONENTE","ANO4","TRIMESTRE","P47T")
OOF_REQUIRED = ("row_id","fold","pred")
RES_REQUIRED = ("outer_fold","residual")


class TelescopeBError(ValueError):
    pass


def require(df, cols, label):
    missing = sorted(set(cols) - set(df.columns))
    if missing:
        raise TelescopeBError(f"{label} missing columns: {missing}")


def period_parts(period):
    try:
        y, q = period.upper().split("-Q")
        y, q = int(y), int(q)
    except (AttributeError, ValueError) as exc:
        raise TelescopeBError("period must be YYYY-Q1..Q4") from exc
    if q not in (1,2,3,4):
        raise TelescopeBError("period must be YYYY-Q1..Q4")
    return y, q


def weighted_mean(values, weights):
    v, w = np.asarray(values,float), np.asarray(weights,float)
    if len(v) != len(w) or not len(v) or not np.isfinite(v).all() or not np.isfinite(w).all() or (w <= 0).any():
        raise TelescopeBError("invalid weighted-mean inputs")
    return float(np.average(v, weights=w))


def ecdf_probability(residuals, cut):
    r, c = np.sort(np.asarray(residuals,float)), np.asarray(cut,float)
    if not len(r) or not np.isfinite(r).all() or not np.isfinite(c).all():
        raise TelescopeBError("invalid residual ECDF inputs")
    return np.searchsorted(r, c, side="right") / len(r)


def state_from_point(welfare, cba, cbt):
    if (cba <= 0).any() or (cbt <= 0).any() or (cba > cbt).any():
        raise TelescopeBError("poverty lines must be positive with CBA <= CBT")
    out = pd.Series("nonpoor", index=welfare.index, dtype=object)
    out[welfare <= cbt] = "poor_non_indigent"
    out[welfare <= cba] = "indigent"
    return out


def universe_weight(frame, universe):
    if universe == "households":
        return frame.PONDIH.astype(float)
    if universe == "persons":
        return frame.PONDIH.astype(float) * frame.member_count_records.astype(float)
    raise TelescopeBError(f"unknown universe {universe}")


def stage_probabilities(frame, stage):
    if stage in ("OBSERVED","OOF_POINT"):
        state = frame.observed_state if stage == "OBSERVED" else frame.point_state
        return {s:(state == s).astype(float).to_numpy() for s in STATES}
    if stage != "PREDICTIVE":
        raise TelescopeBError(f"unknown stage {stage}")
    return {
        "indigent": frame.p_indigent.to_numpy(float),
        "poor_non_indigent": frame.p_poor_non_indigent.to_numpy(float),
        "nonpoor": frame.p_nonpoor.to_numpy(float),
    }


def make_bridge(frame):
    rows = []
    for stage in ("OBSERVED","OOF_POINT","PREDICTIVE"):
        probs = stage_probabilities(frame, stage)
        for universe in ("households","persons"):
            w = universe_weight(frame, universe)
            estimates = {}
            for state in STATES:
                estimate = weighted_mean(probs[state], w)
                estimates[state] = estimate
                rows.append({
                    "stage":stage, "universe":universe, "state":state,
                    "estimate":estimate,
                    "weighted_numerator":float(np.dot(probs[state],w)),
                    "weighted_denominator":float(w.sum()),
                })
            if not math.isclose(sum(estimates.values()), 1.0, abs_tol=1e-12):
                raise TelescopeBError(f"{stage}/{universe} states do not sum to one")
    return pd.DataFrame(rows)


def make_flows(frame):
    rows = []
    for concept,line_col,prob_col in (
        ("indigence","household_cba","p_indigent"),
        ("poverty","household_cbt","p_poor"),
    ):
        q = (frame.point_welfare <= frame[line_col]).astype(float)
        p = frame[prob_col].astype(float)
        for universe in ("households","persons"):
            w = universe_weight(frame, universe)
            den = float(w.sum())
            point = weighted_mean(q,w)
            predictive = weighted_mean(p,w)
            downward = float((w*p*(1-q)).sum()/den)
            upward = float((w*(1-p)*q).sum()/den)
            net = predictive-point
            error = net-(downward-upward)
            if abs(error) > 1e-12:
                raise TelescopeBError(f"{concept}/{universe} flow identity failed")
            rows.append({
                "concept":concept,"universe":universe,"point_rate":point,
                "predictive_rate":predictive,"downward_crossing":downward,
                "upward_crossing":upward,"net_predictive_minus_point":net,
                "identity_error":error,
            })
    return pd.DataFrame(rows)


def make_transitions(frame):
    rows = []
    for universe in ("households","persons"):
        w = universe_weight(frame, universe)
        den = float(w.sum())
        for observed in STATES:
            for point in STATES:
                mask = (frame.observed_state == observed) & (frame.point_state == point)
                mass = float(w[mask].sum())
                rows.append({
                    "universe":universe,"observed_state":observed,"point_state":point,
                    "household_count":int(mask.sum()),"weighted_mass":mass,
                    "weighted_share":mass/den,
                })
    return pd.DataFrame(rows)


def calibration_table(frame, universe, concept, prob_col, event_col, bins):
    if bins < 2:
        raise TelescopeBError("calibration bins must be >=2")
    p = frame[prob_col].astype(float).to_numpy()
    o = frame[event_col].astype(float).to_numpy()
    w = universe_weight(frame, universe).to_numpy(float)
    order = np.argsort(p, kind="stable")
    p,o,w = p[order],o[order],w[order]
    midpoint = np.cumsum(w)-0.5*w
    labels = np.minimum((midpoint/w.sum()*bins).astype(int), bins-1)
    rows = []
    for b in range(bins):
        mask = labels == b
        if mask.any():
            rows.append({
                "universe":universe,"concept":concept,"bin":b+1,
                "households":int(mask.sum()),"weight_mass":float(w[mask].sum()),
                "mean_predicted":weighted_mean(p[mask],w[mask]),
                "observed_rate":weighted_mean(o[mask],w[mask]),
            })
    return pd.DataFrame(rows), weighted_mean((p-o)**2,w)


def build_telescope_b(a_households, eph_persons, person_oof, fold_residuals, *, period="2024-Q3", calibration_bins=5):
    year, quarter = period_parts(period)
    hh, people, oof, residuals = (x.copy() for x in (a_households,eph_persons,person_oof,fold_residuals))
    require(hh,A_REQUIRED,"Telescope-A households")
    require(people,P_REQUIRED,"EPH persons")
    require(oof,OOF_REQUIRED,"person OOF")
    require(residuals,RES_REQUIRED,"fold residuals")

    if hh.empty or hh.household_id.duplicated().any():
        raise TelescopeBError("Telescope-A household identity must be nonempty and unique")
    numeric = ("member_count_records","ITF","sum_P47T","PONDIH","household_cba","household_cbt")
    for c in numeric:
        hh[c] = pd.to_numeric(hh[c], errors="coerce")
    if hh[list(numeric)].isna().any().any():
        raise TelescopeBError("Telescope-A numeric fields must be complete")
    if (hh.PONDIH <= 0).any() or (~np.isfinite(hh.PONDIH)).any():
        raise TelescopeBError("Telescope B requires positive-PONDIH A0")
    complete = hh.P47T_complete
    if complete.dtype != bool:
        complete = complete.astype(str).str.lower().map({"true":True,"false":False})
    if complete.isna().any() or not complete.all():
        raise TelescopeBError("Telescope B requires the P47T-complete A0 cohort")
    if not np.allclose(hh.ITF,hh.sum_P47T,rtol=0,atol=1e-9):
        raise TelescopeBError("Telescope B requires ITF == sum_P47T")
    if (hh.household_cba <= 0).any() or (hh.household_cbt <= 0).any() or (hh.household_cba > hh.household_cbt).any():
        raise TelescopeBError("invalid Telescope-A poverty lines")

    for c in P_REQUIRED:
        people[c] = people[c].astype(str).str.strip()
    y = pd.to_numeric(people.ANO4,errors="coerce")
    q = pd.to_numeric(people.TRIMESTRE,errors="coerce")
    if y.isna().any() or q.isna().any() or set(zip(y.astype(int),q.astype(int))) != {(year,quarter)}:
        raise TelescopeBError("EPH person period mismatch")
    people["household_id"] = people.ANO4+":"+people.TRIMESTRE+":"+people.CODUSU+":"+people.NRO_HOGAR
    people["row_id"] = people.CODUSU+":"+people.NRO_HOGAR+":"+people.COMPONENTE
    if people.row_id.duplicated().any():
        raise TelescopeBError("duplicate EPH person row_id")
    selected = people[people.household_id.isin(set(hh.household_id))].copy()
    if set(selected.household_id) != set(hh.household_id):
        raise TelescopeBError("Telescope-A household/person identity mismatch")
    counts = selected.groupby("household_id").size()
    expected_counts = hh.set_index("household_id").member_count_records.astype(int)
    if not counts.reindex(expected_counts.index).equals(expected_counts):
        raise TelescopeBError("Telescope-A/EPH membership mismatch")
    selected["observed_person_income"] = pd.to_numeric(selected.P47T,errors="coerce")
    if selected.observed_person_income.isna().any() or (selected.observed_person_income < 0).any():
        raise TelescopeBError("Telescope B requires complete nonnegative P47T")
    reconstructed = selected.groupby("household_id").observed_person_income.sum()
    expected = hh.set_index("household_id").sum_P47T
    if not np.allclose(reconstructed.reindex(expected.index),expected,rtol=0,atol=1e-9):
        raise TelescopeBError("raw P47T does not reproduce Telescope-A welfare")

    if oof.row_id.duplicated().any():
        raise TelescopeBError("duplicate OOF row_id")
    oof["fold"] = pd.to_numeric(oof.fold,errors="coerce")
    oof["pred"] = pd.to_numeric(oof.pred,errors="coerce")
    if oof[["fold","pred"]].isna().any().any() or (~np.isfinite(oof.pred)).any() or (oof.pred < 0).any():
        raise TelescopeBError("invalid OOF fold/pred")
    joined = selected[["row_id","household_id"]].merge(oof[["row_id","fold","pred"]],on="row_id",how="left",validate="one_to_one")
    if joined[["fold","pred"]].isna().any().any():
        missing = joined.loc[joined.pred.isna(),"row_id"].head(20).tolist()
        raise TelescopeBError(f"OOF predictions do not exactly cover Telescope-B persons: {missing}")
    if ((joined.fold%1) != 0).any():
        raise TelescopeBError("OOF folds must be integers")
    joined["fold"] = joined.fold.astype(int)
    if (joined.groupby("household_id").fold.nunique() != 1).any():
        raise TelescopeBError("household members cross outer folds")
    point = joined.groupby("household_id").agg(point_welfare=("pred","sum"),outer_fold=("fold","first"),oof_persons=("row_id","size"))

    residuals["outer_fold"] = pd.to_numeric(residuals.outer_fold,errors="coerce")
    residuals["residual"] = pd.to_numeric(residuals.residual,errors="coerce")
    if residuals[["outer_fold","residual"]].isna().any().any() or (~np.isfinite(residuals.residual)).any() or ((residuals.outer_fold%1) != 0).any():
        raise TelescopeBError("invalid fold residuals")
    residuals["outer_fold"] = residuals.outer_fold.astype(int)
    required_folds = set(point.outer_fold.unique())
    missing_folds = required_folds-set(residuals.outer_fold.unique())
    if missing_folds:
        raise TelescopeBError(f"missing nested residual ECDF folds: {sorted(missing_folds)}")

    m = hh.merge(point.reset_index(),on="household_id",validate="one_to_one")
    if not (m.oof_persons.astype(int) == m.member_count_records.astype(int)).all():
        raise TelescopeBError("OOF membership mismatch")
    m["observed_welfare"] = m.sum_P47T.astype(float)
    m["observed_state"] = state_from_point(m.observed_welfare,m.household_cba,m.household_cbt)
    m["point_state"] = state_from_point(m.point_welfare,m.household_cba,m.household_cbt)
    m["p_indigent"],m["p_poor"] = np.nan,np.nan
    residual_counts = {}
    for fold in sorted(required_folds):
        mask = m.outer_fold == fold
        r = residuals.loc[residuals.outer_fold == fold,"residual"].to_numpy(float)
        if not len(r):
            raise TelescopeBError(f"empty residual ECDF for fold {fold}")
        residual_counts[str(fold)] = int(len(r))
        mu = m.loc[mask,"point_welfare"].to_numpy(float)
        m.loc[mask,"p_indigent"] = ecdf_probability(r,m.loc[mask,"household_cba"].to_numpy(float)-mu)
        m.loc[mask,"p_poor"] = ecdf_probability(r,m.loc[mask,"household_cbt"].to_numpy(float)-mu)
    if m[["p_indigent","p_poor"]].isna().any().any() or (m.p_indigent > m.p_poor+1e-15).any():
        raise TelescopeBError("invalid predictive probabilities")
    m["p_poor_non_indigent"] = m.p_poor-m.p_indigent
    m["p_nonpoor"] = 1-m.p_poor
    m["observed_indigent"] = (m.observed_welfare <= m.household_cba).astype(float)
    m["observed_poor"] = (m.observed_welfare <= m.household_cbt).astype(float)
    m["delta_indigence_predictive_minus_point"] = m.p_indigent-(m.point_welfare <= m.household_cba).astype(float)
    m["delta_poverty_predictive_minus_point"] = m.p_poor-(m.point_welfare <= m.household_cbt).astype(float)

    bridge = make_bridge(m)
    flows = make_flows(m)
    transitions = make_transitions(m)
    calibration_parts,brier = [],{}
    for universe in ("households","persons"):
        for concept,prob,event in (("indigence","p_indigent","observed_indigent"),("poverty","p_poor","observed_poor")):
            table,score = calibration_table(m,universe,concept,prob,event,calibration_bins)
            calibration_parts.append(table)
            brier[f"{universe}/{concept}"] = score
    calibration = pd.concat(calibration_parts,ignore_index=True)

    idx = {(r.stage,r.universe,r.state):float(r.estimate) for r in bridge.itertuples()}
    deltas = {}
    for universe in ("households","persons"):
        deltas[universe] = {}
        for state in STATES:
            obs,point_est,pred = idx[("OBSERVED",universe,state)],idx[("OOF_POINT",universe,state)],idx[("PREDICTIVE",universe,state)]
            deltas[universe][state] = {
                "point_minus_observed":point_est-obs,
                "predictive_minus_point":pred-point_est,
                "predictive_minus_observed":pred-obs,
            }

    summary = {
        "status":"RESEARCH_VALIDATION_NOT_OFFICIAL_INDEC_STATISTICS",
        "period":period,
        "scope":"same-household observed P47T -> OOF point -> outer-fold nested residual predictive bridge",
        "b0_identity":{
            "households":int(len(m)),"persons":int(len(selected)),
            "household_pondih_mass":float(m.PONDIH.sum()),
            "person_weight_mass":float((m.PONDIH*m.member_count_records).sum()),
            "observed_welfare":"sum_P47T; exact equality with Telescope-A ITF required",
            "point_welfare":"sum of person-level P1-R OOF predictions",
            "poverty_lines":"exact Telescope-A household CBA/CBT",
            "monetary_reference":"unchanged Q3 nominal source units; no scalar applied",
            "outer_folds":sorted(int(x) for x in required_folds),
            "nested_residual_count_by_outer_fold":residual_counts,
        },
        "bridge":bridge.to_dict("records"),"deltas":deltas,"flows":flows.to_dict("records"),
        "weighted_brier":brier,
        "deferred":["PIT calibration","predictive interval coverage","conditional/heteroskedastic residual ECDF","P2 model arm","FGT1/FGT2","Census transport","multi-quarter validation"],
    }
    return m,bridge,flows,transitions,calibration,summary


def render_report(summary):
    bridge,flows = pd.DataFrame(summary["bridge"]),pd.DataFrame(summary["flows"])
    def pct(stage,universe,state):
        x = bridge[(bridge.stage == stage)&(bridge.universe == universe)&(bridge.state == state)].estimate
        return 100*float(x.iloc[0])
    rows = []
    for universe in ("households","persons"):
        for stage in ("OBSERVED","OOF_POINT","PREDICTIVE"):
            rows.append(f"| {universe} | {stage} | {pct(stage,universe,'indigent'):.3f}% | {pct(stage,universe,'poor_non_indigent'):.3f}% | {pct(stage,universe,'nonpoor'):.3f}% |")
    flow_rows = [f"| {r.universe} | {r.concept} | {100*r.point_rate:.3f}% | +{100*r.downward_crossing:.3f} pp | -{100*r.upward_crossing:.3f} pp | {100*r.net_predictive_minus_point:+.3f} pp | {100*r.predictive_rate:.3f}% |" for r in flows.itertuples()]
    b0 = summary["b0_identity"]
    return f"""# Telescope B — {summary['period']}

> Research validation only; not official INDEC statistics.

## B0 identity lock
- households: {b0['households']}
- persons: {b0['persons']}
- observed welfare: sum_P47T
- point welfare: sum of person OOF predictions
- lines: exact Telescope-A CBA/CBT
- weights: PONDIH
- monetary transformation: none

## B1 same-household bridge
| Universe | Stage | Indigent | Poor non-indigent | Nonpoor |
|---|---|---:|---:|---:|
{chr(10).join(rows)}

## B2 point-to-predictive flows
| Universe | Threshold | Point | Downward | Upward | Net | Predictive |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(flow_rows)}

The flow identity downward - upward = predictive - point is verified exactly.
See threshold_calibration.csv for B3 reliability at the actual CBA/CBT thresholds.
"""


def read_table(path, sep=None):
    suffix = path.suffix.lower()
    if suffix in (".parquet",".pq"):
        return pd.read_parquet(path)
    if suffix in (".jsonl",".ndjson"):
        return pd.read_json(path,lines=True)
    if suffix == ".json":
        return pd.read_json(path)
    return pd.read_csv(path,sep=sep)


def main():
    ap = argparse.ArgumentParser(description="Telescope B same-household predictive poverty diagnostic")
    ap.add_argument("--telescope-a-households",type=Path,required=True)
    ap.add_argument("--eph-persons",type=Path,required=True)
    ap.add_argument("--person-oof",type=Path,required=True)
    ap.add_argument("--fold-residuals",type=Path,required=True)
    ap.add_argument("--period",default="2024-Q3")
    ap.add_argument("--calibration-bins",type=int,default=5)
    ap.add_argument("--output",type=Path,required=True)
    a = ap.parse_args()
    m,bridge,flows,transitions,calibration,summary = build_telescope_b(
        read_table(a.telescope_a_households),read_table(a.eph_persons,sep=";"),
        read_table(a.person_oof),read_table(a.fold_residuals),
        period=a.period,calibration_bins=a.calibration_bins,
    )
    a.output.mkdir(parents=True,exist_ok=True)
    m.to_parquet(a.output/"households.parquet",index=False)
    bridge.to_csv(a.output/"bridge.csv",index=False)
    flows.to_csv(a.output/"flows.csv",index=False)
    transitions.to_csv(a.output/"point_transitions.csv",index=False)
    calibration.to_csv(a.output/"threshold_calibration.csv",index=False)
    (a.output/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True))
    (a.output/"report.md").write_text(render_report(summary))
    print(json.dumps({"status":summary["status"],"period":a.period,"households":len(m),"output":str(a.output)},indent=2))


if __name__ == "__main__":
    main()
