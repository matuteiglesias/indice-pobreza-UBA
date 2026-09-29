"""Observed-EPH poverty replication for CEDLAS DT370 updated-consumption scenario."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from .core import (
    AlignmentError,
    aggregate_contributions,
    assert_t0_reproduces_telescope,
    contribution_frame,
    load_telescope_households,
    quarter_months,
    semester_id,
    transition_rows,
)

CEDLAS_ARTIFACT_TYPE="research.argentina-regional-baskets-cedlas-dt370-replication/v1"
CEDLAS_METHOD_ID="research.argentina-regional-baskets-cedlas-dt370/published-low-education-v1"
POLICIES=("official","cedlas_updated_consumption")
REGIONS=("gran_buenos_aires","pampeana","noreste","noroeste","cuyo","patagonia")


def _manifest(root: Path) -> tuple[dict,str]:
    path=root/"manifest.json"
    if not path.is_file():
        raise AlignmentError("CEDLAS replication manifest missing")
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def load_cedlas_replication(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest,manifest_sha=_manifest(root)
    if manifest.get("artifact_type")!=CEDLAS_ARTIFACT_TYPE or manifest.get("method_id")!=CEDLAS_METHOD_ID:
        raise AlignmentError("wrong CEDLAS replication artifact")
    if manifest.get("scientific_poverty_execution_performed") is not False:
        raise AlignmentError("CEDLAS threshold parent must be poverty-free")
    path=root/"threshold_paths.csv"
    frame=pd.read_csv(path,dtype=str)
    required={"period","region_id","CBA_official","CBT_official","CBT_cedlas"}
    if not required.issubset(frame.columns):
        raise AlignmentError(f"CEDLAS threshold columns missing: {sorted(required-set(frame.columns))}")
    frame["period"]=pd.to_datetime(frame["period"],errors="raise").dt.to_period("M").dt.to_timestamp()
    for col in ("CBA_official","CBT_official","CBT_cedlas"):
        frame[col]=pd.to_numeric(frame[col],errors="raise")
    if frame.duplicated(["period","region_id"]).any():
        raise AlignmentError("duplicate CEDLAS month/region")
    return {"root":root,"manifest":manifest,"manifest_sha256":manifest_sha,"frame":frame}


def _mean(frame: pd.DataFrame, months: list[pd.Timestamp], region: str, field: str) -> float:
    rows=frame[(frame["period"].isin(months))&(frame["region_id"]==region)]
    if len(rows)!=len(months) or set(rows["period"])!=set(months):
        raise AlignmentError(f"missing CEDLAS line cells: {region}/{field}")
    return float(rows.set_index("period").loc[months,field].astype(float).mean())


def quarter_lines(artifact: dict, period: str) -> dict[str,dict[str,dict[str,float]]]:
    months=quarter_months(period)
    out={p:{} for p in POLICIES}
    for region in REGIONS:
        cba=_mean(artifact["frame"],months,region,"CBA_official")
        out["official"][region]={
            "cba_per_ae":cba,
            "cbt_per_ae":_mean(artifact["frame"],months,region,"CBT_official"),
        }
        out["cedlas_updated_consumption"][region]={
            "cba_per_ae":cba,
            "cbt_per_ae":_mean(artifact["frame"],months,region,"CBT_cedlas"),
        }
    return out


def _external_comparison(semester: pd.DataFrame, targets: Path) -> pd.DataFrame:
    t=pd.read_csv(targets)
    rows=[]
    obs=semester[
        (semester["geography_level"]=="national")&
        (semester["geography_id"]=="ARG")&
        (semester["universe"]=="persons")&
        (semester["concept"]=="poverty")&
        (semester["estimand"]=="fgt0")&
        (semester["policy"]=="cedlas_updated_consumption")
    ]
    for row in obs.itertuples():
        target=t[t["semester"]==row.period]
        if target.empty:
            continue
        published=float(target.iloc[0]["updated_consumption_person_poverty"])
        rows.append({
            "semester":row.period,
            "our_estimate":float(row.estimate),
            "published_cedlas":published,
            "difference":float(row.estimate)-published,
            "difference_pp":100*(float(row.estimate)-published),
            "within_0_1pp":abs(float(row.estimate)-published)<=0.001,
            "role":"replication_validation_not_estimator_input",
        })
    return pd.DataFrame(rows)


def run_cedlas_poverty_replication(config: dict) -> dict:
    artifact=load_cedlas_replication(Path(config["cedlas_replication_release"]))
    specs=config.get("periods") or []
    if not specs:
        raise AlignmentError("CEDLAS poverty config needs periods")
    qrows=[]; transitions=[]; contributions={}
    for spec in specs:
        period=spec["period"]
        hh=load_telescope_households(Path(spec["telescope_a_households"]),period)
        lines=quarter_lines(artifact,period)
        assert_t0_reproduces_telescope(hh,lines["official"])
        baseline=None
        for policy in POLICIES:
            cf=contribution_frame(hh,lines[policy],experiment="M3R_CEDLAS",policy=policy)
            contributions[(period,policy)]=cf
            qrows.extend(aggregate_contributions(cf,period_label=period))
            if policy=="official":
                baseline=cf
            else:
                transitions.extend(transition_rows(baseline,cf,period=period))
    qdf=pd.DataFrame(qrows)
    periods={s["period"] for s in specs}
    sem=[]
    for sid in sorted({semester_id(p) for p in periods}):
        year=int(sid[:4]); sn=int(sid[-1])
        req={f"{year}-Q{1 if sn==1 else 3}",f"{year}-Q{2 if sn==1 else 4}"}
        if not req.issubset(periods):
            continue
        for policy in POLICIES:
            pooled=pd.concat([contributions[(p,policy)] for p in sorted(req)],ignore_index=True)
            sem.extend(aggregate_contributions(pooled,period_label=sid))
    sdf=pd.DataFrame(sem)
    targets=Path(config.get("external_targets","science/measurement_alignment/external_targets/cedlas_dt370_table5.csv"))
    ext=_external_comparison(sdf,targets)
    max_abs=float(ext["difference_pp"].abs().max()) if not ext.empty else None
    return {
        "quarterly_estimates":qdf,
        "semester_estimates":sdf,
        "transitions":pd.DataFrame(transitions),
        "external_comparison":ext,
        "qa":{
            "status":"pass" if max_abs is not None and max_abs<=0.1 else "diagnostic_mismatch",
            "telescope_a_baseline_reproduction":"pass",
            "max_abs_table5_difference_pp":max_abs,
            "target_tolerance_pp":0.1,
            "all_published_semesters_within_tolerance":bool(not ext.empty and ext["within_0_1pp"].all()),
            "cedlas_release_id":artifact["manifest"].get("release_id"),
            "cedlas_manifest_sha256":artifact["manifest_sha256"],
            "coicop02_food_fraction":artifact["manifest"].get("coicop02_food_fraction"),
            "tobacco_in_food":artifact["manifest"].get("tobacco_in_food"),
            "regionalization":artifact["manifest"].get("regionalization"),
            "official_basket_release_id":artifact["manifest"].get("official_basket_release_id"),
            "welfare_changed":False,
            "cba_changed":False,
            "m2_reporting_drift":"deferred",
            "nonresponse_calibration_performed":False,
        }
    }
