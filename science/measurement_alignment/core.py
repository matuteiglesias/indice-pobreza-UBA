"""Core mechanics for observed-EPH M1 timing and M3 ENGHo/Engel alignment."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .contracts import (
    BASKET_ARTIFACT_TYPE, BASKET_METHOD_ID, BASELINE_POLICY,
    ENGEL_ARTIFACT_TYPE, ENGEL_METHOD_ID, ENGEL_REFERENCE_METHOD_ID,
    M1_POLICIES, M3_POLICIES, REGIONS, STATUS,
)

REQUIRED_HOUSEHOLD_COLUMNS = (
    "period", "household_id", "basket_region", "adult_equivalents", "ITF",
    "PONDIH", "member_count_records", "cba_per_ae", "cbt_per_ae",
)


class AlignmentError(ValueError):
    pass


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def quarter_months(period: str) -> list[pd.Timestamp]:
    try:
        year_s,q_s=period.upper().split("-Q")
        year,q=int(year_s),int(q_s)
    except Exception as exc:
        raise AlignmentError(f"invalid quarter: {period}") from exc
    if q not in (1,2,3,4):
        raise AlignmentError(f"invalid quarter: {period}")
    first=1+(q-1)*3
    return [pd.Timestamp(year,m,1) for m in range(first,first+3)]


def previous_month(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts-pd.offsets.MonthBegin(1)).normalize().replace(day=1)


def semester_id(period: str) -> str:
    year=int(period[:4]); q=int(period[-1])
    return f"{year}-S{1 if q<=2 else 2}"


def _read_manifest(root: Path) -> tuple[dict,str]:
    path=root/"manifest.json"
    if not path.is_file():
        raise AlignmentError(f"missing manifest: {root}")
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def load_official_baskets(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest,manifest_sha=_read_manifest(root)
    if manifest.get("artifact_type")!=BASKET_ARTIFACT_TYPE or manifest.get("method_id")!=BASKET_METHOD_ID:
        raise AlignmentError("official basket parent identity mismatch")
    path=root/"observed_nominal_monthly.csv"
    if not path.is_file():
        raise AlignmentError("official basket monthly table missing")
    frame=pd.read_csv(path,dtype=str)
    required={"period","region_id","CBA_nominal","CBT_nominal"}
    if not required.issubset(frame.columns):
        raise AlignmentError(f"basket columns missing: {sorted(required-set(frame.columns))}")
    frame["period"]=pd.to_datetime(frame["period"],errors="raise").dt.to_period("M").dt.to_timestamp()
    frame["CBA_nominal"]=pd.to_numeric(frame["CBA_nominal"],errors="raise")
    frame["CBT_nominal"]=pd.to_numeric(frame["CBT_nominal"],errors="raise")
    if frame.duplicated(["period","region_id"]).any():
        raise AlignmentError("duplicate official basket month/region")
    if not set(frame["region_id"]).issubset(set(REGIONS)):
        raise AlignmentError("unknown basket region")
    if (frame["CBA_nominal"]<=0).any() or (frame["CBT_nominal"]<=0).any() or (frame["CBA_nominal"]>frame["CBT_nominal"]).any():
        raise AlignmentError("invalid official basket values")
    return {"root":root,"manifest":manifest,"manifest_sha256":manifest_sha,"frame":frame}


def load_engel_artifact(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest,manifest_sha=_read_manifest(root)
    if manifest.get("artifact_type")!=ENGEL_ARTIFACT_TYPE or manifest.get("method_id")!=ENGEL_METHOD_ID:
        raise AlignmentError("ENGHo sensitivity parent identity mismatch")
    locks=json.loads((root/"parent_locks.json").read_text(encoding="utf-8"))
    ref=locks.get("engho_reference",{})
    if ref.get("method_id")!=ENGEL_REFERENCE_METHOD_ID:
        raise AlignmentError("M3 requires signed-sales Artifact-A parent")
    path=root/"threshold_paths.csv"
    if not path.is_file():
        raise AlignmentError("ENGHo threshold_paths.csv missing")
    frame=pd.read_csv(path,dtype=str)
    required={"period","region_id","CBA_official","CBT_official","CBT_level_only","CBT_level_plus_trajectory"}
    if not required.issubset(frame.columns):
        raise AlignmentError(f"ENGHo path columns missing: {sorted(required-set(frame.columns))}")
    frame["period"]=pd.to_datetime(frame["period"],errors="raise").dt.to_period("M").dt.to_timestamp()
    for col in ("CBA_official","CBT_official","CBT_level_only","CBT_level_plus_trajectory"):
        frame[col]=pd.to_numeric(frame[col],errors="raise")
        if (frame[col]<=0).any():
            raise AlignmentError(f"invalid ENGHo threshold values: {col}")
    if frame.duplicated(["period","region_id"]).any():
        raise AlignmentError("duplicate ENGHo month/region")
    return {"root":root,"manifest":manifest,"manifest_sha256":manifest_sha,"locks":locks,"frame":frame}


def _monthly_lookup(frame: pd.DataFrame, months: list[pd.Timestamp], region: str, field: str) -> float:
    rows=frame[(frame["period"].isin(months)) & (frame["region_id"]==region)]
    if len(rows)!=len(months) or set(rows["period"])!=set(months):
        raise AlignmentError(f"missing monthly line cells for {region}/{field}/{[str(x.date()) for x in months]}")
    values=rows.set_index("period").loc[months,field].astype(float)
    if not np.isfinite(values).all() or (values<=0).any():
        raise AlignmentError(f"invalid line cells for {region}/{field}")
    return float(values.mean())


def m1_lines(baskets: dict, period: str) -> dict[str,dict[str,dict[str,float]]]:
    months=quarter_months(period)
    lag=[previous_month(m) for m in months]
    result={}
    for policy in M1_POLICIES:
        result[policy]={}
        for region in REGIONS:
            current_cba=_monthly_lookup(baskets["frame"],months,region,"CBA_nominal")
            current_cbt=_monthly_lookup(baskets["frame"],months,region,"CBT_nominal")
            lag_cba=_monthly_lookup(baskets["frame"],lag,region,"CBA_nominal")
            lag_cbt=_monthly_lookup(baskets["frame"],lag,region,"CBT_nominal")
            if policy==M1_POLICIES[0]:
                cba,cbt=current_cba,current_cbt
            elif policy==M1_POLICIES[1]:
                cba,cbt=lag_cba,lag_cbt
            else:
                cba,cbt=(current_cba+lag_cba)/2,(current_cbt+lag_cbt)/2
            result[policy][region]={"cba_per_ae":cba,"cbt_per_ae":cbt}
    return result


def m3_lines(engel: dict, period: str) -> dict[str,dict[str,dict[str,float]]]:
    months=quarter_months(period)
    fields={
        "official":"CBT_official",
        "engho17_level_only":"CBT_level_only",
        "engho17_level_plus_trajectory":"CBT_level_plus_trajectory",
    }
    result={policy:{} for policy in M3_POLICIES}
    for region in REGIONS:
        cba=_monthly_lookup(engel["frame"],months,region,"CBA_official")
        for policy,field in fields.items():
            result[policy][region]={
                "cba_per_ae":cba,
                "cbt_per_ae":_monthly_lookup(engel["frame"],months,region,field),
            }
    return result


def load_telescope_households(path: Path, period: str) -> pd.DataFrame:
    frame=pd.read_parquet(path).copy()
    missing=set(REQUIRED_HOUSEHOLD_COLUMNS)-set(frame.columns)
    if missing:
        raise AlignmentError(f"Telescope A household columns missing: {sorted(missing)}")
    if set(frame["period"].astype(str))!={period}:
        raise AlignmentError(f"Telescope A period mismatch for {period}")
    if frame["household_id"].duplicated().any():
        raise AlignmentError(f"duplicate Telescope A household IDs in {period}")
    if not set(frame["basket_region"]).issubset(set(REGIONS)):
        raise AlignmentError(f"unknown Telescope A basket region in {period}")
    for col in ("adult_equivalents","ITF","PONDIH","member_count_records","cba_per_ae","cbt_per_ae"):
        frame[col]=pd.to_numeric(frame[col],errors="raise")
    if (frame["adult_equivalents"]<=0).any() or (frame["ITF"]<0).any() or (frame["PONDIH"]<=0).any() or (frame["member_count_records"]<=0).any():
        raise AlignmentError(f"invalid Telescope A analytical values in {period}")
    return frame


def assert_t0_reproduces_telescope(frame: pd.DataFrame, lines: dict, *, tolerance: float=1e-9) -> None:
    for region in sorted(frame["basket_region"].unique()):
        rows=frame[frame["basket_region"]==region]
        for col,key in (("cba_per_ae","cba_per_ae"),("cbt_per_ae","cbt_per_ae")):
            observed=rows[col].to_numpy(float)
            target=float(lines[region][key])
            if not np.allclose(observed,target,rtol=tolerance,atol=tolerance):
                raise AlignmentError(f"T0 does not reproduce Telescope A {col} for {region}")


def contribution_frame(frame: pd.DataFrame, lines: dict, *, experiment: str, policy: str) -> pd.DataFrame:
    out=frame[["period","household_id","basket_region","adult_equivalents","ITF","PONDIH","member_count_records"]].copy()
    out["experiment"]=experiment; out["policy"]=policy
    out["cba_per_ae"]=out["basket_region"].map({r:v["cba_per_ae"] for r,v in lines.items()})
    out["cbt_per_ae"]=out["basket_region"].map({r:v["cbt_per_ae"] for r,v in lines.items()})
    if out[["cba_per_ae","cbt_per_ae"]].isna().any().any():
        raise AlignmentError("unmapped threshold region")
    out["household_cba"]=out["adult_equivalents"]*out["cba_per_ae"]
    out["household_cbt"]=out["adult_equivalents"]*out["cbt_per_ae"]
    for concept,line_col in (("indigence","household_cba"),("poverty","household_cbt")):
        line=out[line_col]
        gap=((line-out["ITF"])/line).clip(lower=0)
        out[f"{concept}_fgt0"]=(gap>0).astype(float)
        out[f"{concept}_fgt1"]=gap
        out[f"{concept}_fgt2"]=gap*gap
    return out


def aggregate_contributions(frame: pd.DataFrame, *, period_label: str) -> list[dict]:
    rows=[]
    geographies=[("national","ARG",frame)]
    geographies += [("eph_region",r,frame[frame["basket_region"]==r]) for r in REGIONS if (frame["basket_region"]==r).any()]
    for level,gid,g in geographies:
        for universe,weight in (
            ("households",g["PONDIH"]),
            ("persons",g["PONDIH"]*g["member_count_records"]),
        ):
            denom=float(weight.sum())
            if denom<=0:
                raise AlignmentError("nonpositive alignment denominator")
            for concept in ("indigence","poverty"):
                for estimand in ("fgt0","fgt1","fgt2"):
                    values=g[f"{concept}_{estimand}"].astype(float)
                    estimate=float(np.average(values,weights=weight))
                    rows.append({
                        "period":period_label,
                        "experiment":str(g["experiment"].iloc[0]),
                        "policy":str(g["policy"].iloc[0]),
                        "geography_level":level,
                        "geography_id":gid,
                        "universe":universe,
                        "concept":concept,
                        "estimand":estimand,
                        "estimate":estimate,
                        "weighted_denominator":denom,
                        "household_records":int(len(g)),
                    })
    return rows


def transition_rows(baseline: pd.DataFrame, candidate: pd.DataFrame, *, period: str) -> list[dict]:
    if list(baseline["household_id"])!=list(candidate["household_id"]):
        raise AlignmentError("transition cohort mismatch")
    rows=[]
    for concept in ("indigence","poverty"):
        before=baseline[f"{concept}_fgt0"].astype(bool).to_numpy()
        after=candidate[f"{concept}_fgt0"].astype(bool).to_numpy()
        for b in (False,True):
            for a in (False,True):
                mask=(before==b)&(after==a)
                sub=candidate.loc[mask]
                rows.append({
                    "period":period,
                    "experiment":str(candidate["experiment"].iloc[0]),
                    "policy":str(candidate["policy"].iloc[0]),
                    "concept":concept,
                    "transition":f"{str(b).lower()}_to_{str(a).lower()}",
                    "households":int(mask.sum()),
                    "pondih_mass":float(sub["PONDIH"].sum()),
                    "person_weight_mass":float((sub["PONDIH"]*sub["member_count_records"]).sum()),
                })
    return rows


def external_comparison(semester_estimates: pd.DataFrame, targets_path: Path) -> pd.DataFrame:
    targets=pd.read_csv(targets_path)
    observed=semester_estimates[
        (semester_estimates["geography_level"]=="national") &
        (semester_estimates["geography_id"]=="ARG") &
        (semester_estimates["universe"]=="persons") &
        (semester_estimates["concept"]=="poverty") &
        (semester_estimates["estimand"]=="fgt0")
    ]
    mappings=[
        ("M1","T0_current_quarter_mean","baseline_person_poverty","baseline"),
        ("M1","Tm_current_previous_midpoint","timing_midpoint_person_poverty","timing_midpoint"),
        ("M3","official","baseline_person_poverty","baseline"),
        ("M3","engho17_level_plus_trajectory","updated_consumption_person_poverty","updated_consumption"),
    ]
    out=[]
    for experiment,policy,target_col,label in mappings:
        subset=observed[(observed["experiment"]==experiment)&(observed["policy"]==policy)]
        for row in subset.itertuples():
            target=targets[targets["semester"]==row.period]
            if target.empty or pd.isna(target.iloc[0][target_col]):
                continue
            published=float(target.iloc[0][target_col])
            out.append({
                "semester":row.period,"experiment":experiment,"policy":policy,
                "comparison_label":label,"our_estimate":float(row.estimate),
                "published_validation_target":published,
                "difference":float(row.estimate)-published,
                "role":"validation_only_not_estimator_input",
            })
    return pd.DataFrame(out)


def run_alignment(config: dict) -> dict:
    baskets=load_official_baskets(Path(config["official_basket_release"]))
    engel=load_engel_artifact(Path(config["engel_sensitivity_release"]))
    period_specs=config.get("periods",[])
    if not period_specs:
        raise AlignmentError("config needs periods")
    quarters=[]; transitions=[]; line_rows=[]; contributions={}
    for spec in period_specs:
        period=spec["period"]
        hh=load_telescope_households(Path(spec["telescope_a_households"]),period)
        m1=m1_lines(baskets,period)
        assert_t0_reproduces_telescope(hh,m1[BASELINE_POLICY["M1"]])
        m3=m3_lines(engel,period)
        assert_t0_reproduces_telescope(hh,m3[BASELINE_POLICY["M3"]])
        for experiment,policies in (("M1",m1),("M3",m3)):
            baseline=None
            for policy,lines in policies.items():
                cf=contribution_frame(hh,lines,experiment=experiment,policy=policy)
                contributions[(period,experiment,policy)]=cf
                quarters.extend(aggregate_contributions(cf,period_label=period))
                for region,vals in lines.items():
                    line_rows.append({"period":period,"experiment":experiment,"policy":policy,"region_id":region,**vals})
                if policy==BASELINE_POLICY[experiment]:
                    baseline=cf
                else:
                    transitions.extend(transition_rows(baseline,cf,period=period))
    qdf=pd.DataFrame(quarters)
    sem_rows=[]
    periods={x["period"] for x in period_specs}
    for sid in sorted({semester_id(p) for p in periods}):
        year=int(sid[:4]); sem=int(sid[-1])
        required={f"{year}-Q{1 if sem==1 else 3}",f"{year}-Q{2 if sem==1 else 4}"}
        if not required.issubset(periods):
            continue
        for experiment,policies in (("M1",M1_POLICIES),("M3",M3_POLICIES)):
            for policy in policies:
                pooled=pd.concat([contributions[(p,experiment,policy)] for p in sorted(required)],ignore_index=True)
                sem_rows.extend(aggregate_contributions(pooled,period_label=sid))
    sdf=pd.DataFrame(sem_rows)
    ext_path=Path(config.get("external_targets","science/measurement_alignment/external_targets/cedlas_dt370_table5.csv"))
    external=external_comparison(sdf,ext_path) if not sdf.empty and ext_path.exists() else pd.DataFrame()
    return {
        "quarterly_estimates":qdf,
        "semester_estimates":sdf,
        "transitions":pd.DataFrame(transitions),
        "line_policies":pd.DataFrame(line_rows),
        "external_comparison":external,
        "qa":{
            "status":"pass",
            "telescope_a_baseline_reproduction":"pass",
            "semester_method":"pooled_household_contributions_not_average_of_quarter_rates",
            "m1_welfare_changed":False,
            "m3_welfare_changed":False,
            "m3_cba_changed":False,
            "m2_reporting_drift": "deferred",
            "nonresponse_calibration_performed":False,
            "official_basket_release_id":baskets["manifest"].get("release_id"),
            "official_basket_manifest_sha256":baskets["manifest_sha256"],
            "engel_sensitivity_release_id":engel["manifest"].get("release_id"),
            "engel_sensitivity_manifest_sha256":engel["manifest_sha256"],
            "engel_reference_release_id":engel["manifest"].get("engho_reference_release_id"),
            "engel_reference_method_id":engel["locks"]["engho_reference"]["method_id"],
            "scientific_status":STATUS,
        },
    }
