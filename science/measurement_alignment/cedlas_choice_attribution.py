"""Observed-EPH poverty attribution across forensic CEDLAS methodological choices."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .core import (
    AlignmentError,
    aggregate_contributions,
    assert_t0_reproduces_telescope,
    contribution_frame,
    load_engel_artifact,
    load_telescope_households,
    quarter_months,
    semester_id,
    transition_rows,
)

CHOICE_ARTIFACT_TYPE="research.argentina-regional-baskets-cedlas-choice-attribution/v1"
CHOICE_METHOD_ID="research.argentina-regional-baskets-cedlas-choice-attribution/v1"
REGIONS=("gran_buenos_aires","pampeana","noreste","noroeste","cuyo","patagonia")
PRIMARY_VARIANT="paper_exact"
PRIMARY_P29_VARIANT="primary_p29_p48_full"


def _manifest(root: Path) -> tuple[dict,str]:
    path=root/"manifest.json"
    if not path.is_file():
        raise AlignmentError("CEDLAS choice manifest missing")
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def load_choice_artifact(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest,manifest_sha=_manifest(root)
    if manifest.get("artifact_type")!=CHOICE_ARTIFACT_TYPE or manifest.get("method_id")!=CHOICE_METHOD_ID:
        raise AlignmentError("wrong CEDLAS choice artifact")
    if manifest.get("scientific_poverty_execution_performed") is not False:
        raise AlignmentError("CEDLAS choice parent must be poverty-free")
    paths=root/"threshold_paths.csv"
    variants=root/"variants.csv"
    if not paths.is_file() or not variants.is_file():
        raise AlignmentError("CEDLAS choice artifact incomplete")
    frame=pd.read_csv(paths,dtype=str)
    meta=pd.read_csv(variants,dtype=str)
    required={"variant_id","period","region_id","CBA_official","CBT_official","CBT_variant"}
    if not required.issubset(frame.columns):
        raise AlignmentError(f"CEDLAS choice threshold columns missing: {sorted(required-set(frame.columns))}")
    frame["period"]=pd.to_datetime(frame["period"],errors="raise").dt.to_period("M").dt.to_timestamp()
    for col in ("CBA_official","CBT_official","CBT_variant"):
        frame[col]=pd.to_numeric(frame[col],errors="raise")
    if frame.duplicated(["variant_id","period","region_id"]).any():
        raise AlignmentError("duplicate CEDLAS choice variant/month/region")
    variant_ids=tuple(meta["variant_id"].astype(str))
    if PRIMARY_VARIANT not in variant_ids:
        raise AlignmentError("CEDLAS choice artifact missing paper_exact")
    if set(frame["variant_id"].astype(str))!=set(variant_ids):
        raise AlignmentError("CEDLAS choice variant inventory mismatch")
    return {
        "root":root,
        "manifest":manifest,
        "manifest_sha256":manifest_sha,
        "frame":frame,
        "meta":meta,
        "variant_ids":variant_ids,
    }


def _mean(frame: pd.DataFrame, months: list[pd.Timestamp], region: str, field: str, *, variant: str|None=None) -> float:
    rows=frame[(frame["period"].isin(months))&(frame["region_id"]==region)]
    if variant is not None:
        rows=rows[rows["variant_id"]==variant]
    if len(rows)!=len(months) or set(rows["period"])!=set(months):
        raise AlignmentError(f"missing choice line cells: {variant}/{region}/{field}")
    vals=rows.set_index("period").loc[months,field].astype(float)
    return float(vals.mean())


def _choice_lines(artifact: dict, period: str) -> tuple[dict[str,dict[str,dict[str,float]]],dict[str,dict[str,float]]]:
    months=quarter_months(period)
    out={v:{} for v in artifact["variant_ids"]}
    official={}
    for region in REGIONS:
        official[region]={
            "cba_per_ae":_mean(artifact["frame"],months,region,"CBA_official",variant=PRIMARY_VARIANT),
            "cbt_per_ae":_mean(artifact["frame"],months,region,"CBT_official",variant=PRIMARY_VARIANT),
        }
        for variant in artifact["variant_ids"]:
            out[variant][region]={
                "cba_per_ae":official[region]["cba_per_ae"],
                "cbt_per_ae":_mean(artifact["frame"],months,region,"CBT_variant",variant=variant),
            }
    return out,official


def _primary_p29_lines(engel: dict, period: str) -> dict[str,dict[str,float]]:
    months=quarter_months(period)
    frame=engel["frame"]
    out={}
    for region in REGIONS:
        rows=frame[(frame["period"].isin(months))&(frame["region_id"]==region)]
        if len(rows)!=len(months) or set(rows["period"])!=set(months):
            raise AlignmentError(f"missing primary p29-p48 month cells: {region}")
        by=rows.set_index("period").loc[months]
        out[region]={
            "cba_per_ae":float(by["CBA_official"].astype(float).mean()),
            "cbt_per_ae":float(by["CBT_level_plus_trajectory"].astype(float).mean()),
        }
    return out


def _national_person_fgt0(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (frame["geography_level"]=="national")&
        (frame["geography_id"]=="ARG")&
        (frame["universe"]=="persons")&
        (frame["concept"]=="poverty")&
        (frame["estimand"]=="fgt0")
    ].copy()


def _attribution_table(semester: pd.DataFrame, meta: pd.DataFrame, targets: Path|None) -> pd.DataFrame:
    obs=_national_person_fgt0(semester)
    paper=obs[obs["policy"]==PRIMARY_VARIANT][["period","estimate"]].rename(columns={"estimate":"paper_exact_poverty"})
    primary=obs[obs["policy"]==PRIMARY_P29_VARIANT][["period","estimate"]].rename(columns={"estimate":"primary_p29_p48_poverty"})
    rows=[]
    meta_by={r.variant_id:r for r in meta.itertuples()}
    target_df=pd.read_csv(targets) if targets is not None and Path(targets).exists() else None
    for row in obs.itertuples():
        if row.policy in ("official",PRIMARY_P29_VARIANT):
            continue
        p=float(paper[paper["period"]==row.period].iloc[0]["paper_exact_poverty"])
        pp=float(primary[primary["period"]==row.period].iloc[0]["primary_p29_p48_poverty"])
        m=meta_by.get(row.policy)
        published=None
        if row.policy==PRIMARY_VARIANT and target_df is not None:
            hit=target_df[target_df["semester"]==row.period]
            if not hit.empty:
                published=float(hit.iloc[0]["updated_consumption_person_poverty"])
        rows.append({
            "semester":row.period,
            "variant_id":row.policy,
            "person_poverty":float(row.estimate),
            "delta_vs_paper_exact_pp":100*(float(row.estimate)-p),
            "delta_vs_primary_p29_p48_pp":100*(float(row.estimate)-pp),
            "paper_exact_poverty":p,
            "primary_p29_p48_poverty":pp,
            "reference_population_structure":getattr(m,"reference_population_structure",None) if m is not None else None,
            "regionalization":getattr(m,"regionalization",None) if m is not None else None,
            "coicop02_food_fraction":getattr(m,"coicop02_food_fraction",None) if m is not None else None,
            "published_cedlas":published,
            "paper_exact_difference_to_published_pp":(
                100*(float(row.estimate)-published)
                if published is not None else None
            ),
        })
    return pd.DataFrame(rows)


def run_cedlas_choice_attribution(config: dict) -> dict:
    choice=load_choice_artifact(Path(config["cedlas_choice_release"]))
    primary=load_engel_artifact(Path(config["primary_engel_sensitivity_release"]))
    if choice["manifest"].get("basket_release_id") != primary["manifest"].get("official_basket_release_id"):
        raise AlignmentError("choice and primary p29-p48 artifacts use different official basket parents")
    specs=config.get("periods") or []
    if not specs:
        raise AlignmentError("CEDLAS choice poverty config needs periods")

    qrows=[]; transitions=[]; contributions={}
    for spec in specs:
        period=spec["period"]
        hh=load_telescope_households(Path(spec["telescope_a_households"]),period)
        variants,official=_choice_lines(choice,period)
        assert_t0_reproduces_telescope(hh,official)
        p29=_primary_p29_lines(primary,period)

        baseline=contribution_frame(hh,official,experiment="M3F_CEDLAS_CHOICES",policy="official")
        contributions[(period,"official")]=baseline
        qrows.extend(aggregate_contributions(baseline,period_label=period))

        for variant,lines in variants.items():
            cf=contribution_frame(hh,lines,experiment="M3F_CEDLAS_CHOICES",policy=variant)
            contributions[(period,variant)]=cf
            qrows.extend(aggregate_contributions(cf,period_label=period))
            transitions.extend(transition_rows(baseline,cf,period=period))

        cf=contribution_frame(hh,p29,experiment="M3F_CEDLAS_CHOICES",policy=PRIMARY_P29_VARIANT)
        contributions[(period,PRIMARY_P29_VARIANT)]=cf
        qrows.extend(aggregate_contributions(cf,period_label=period))
        transitions.extend(transition_rows(baseline,cf,period=period))

    qdf=pd.DataFrame(qrows)
    periods={s["period"] for s in specs}
    policies=("official",)+choice["variant_ids"]+(PRIMARY_P29_VARIANT,)
    sem=[]
    for sid in sorted({semester_id(p) for p in periods}):
        year=int(sid[:4]); sn=int(sid[-1])
        required={f"{year}-Q{1 if sn==1 else 3}",f"{year}-Q{2 if sn==1 else 4}"}
        if not required.issubset(periods):
            continue
        for policy in policies:
            pooled=pd.concat([contributions[(p,policy)] for p in sorted(required)],ignore_index=True)
            sem.extend(aggregate_contributions(pooled,period_label=sid))
    sdf=pd.DataFrame(sem)
    targets=Path(config.get("external_targets","science/measurement_alignment/external_targets/cedlas_dt370_table5.csv"))
    attribution=_attribution_table(sdf,choice["meta"],targets)

    paper=attribution[attribution["variant_id"]==PRIMARY_VARIANT]
    max_paper_error=None
    if not paper.empty and paper["paper_exact_difference_to_published_pp"].notna().any():
        max_paper_error=float(paper["paper_exact_difference_to_published_pp"].dropna().abs().max())

    return {
        "quarterly_estimates":qdf,
        "semester_estimates":sdf,
        "transitions":pd.DataFrame(transitions),
        "attribution":attribution,
        "qa":{
            "status":"pass" if max_paper_error is not None and max_paper_error<=0.1 else "diagnostic_mismatch",
            "telescope_a_baseline_reproduction":"pass",
            "choice_release_id":choice["manifest"].get("release_id"),
            "choice_manifest_sha256":choice["manifest_sha256"],
            "primary_engel_release_id":primary["manifest"].get("release_id"),
            "primary_engel_manifest_sha256":primary["manifest_sha256"],
            "official_basket_release_id":choice["manifest"].get("basket_release_id"),
            "variant_count":len(choice["variant_ids"])+1,
            "paper_exact_max_abs_table5_difference_pp":max_paper_error,
            "paper_exact_target_tolerance_pp":0.1,
            "welfare_changed":False,
            "cba_changed":False,
            "m2_reporting_drift":"deferred",
            "nonresponse_calibration_performed":False,
        }
    }
