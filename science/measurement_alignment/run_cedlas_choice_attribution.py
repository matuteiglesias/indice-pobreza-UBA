#!/usr/bin/env python3
"""Materialize Poverty-side forensic attribution across CEDLAS methodological choices."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .cedlas_choice_attribution import run_cedlas_choice_attribution


def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _write(frame: pd.DataFrame, path: Path) -> None:
    if frame.empty:
        path.write_text("",encoding="utf-8")
    else:
        frame.to_csv(path,index=False)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()

    cfg=json.loads(args.config.read_text(encoding="utf-8"))
    result=run_cedlas_choice_attribution(cfg)
    out=args.output.expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    frames={
        "quarterly_estimates.csv":result["quarterly_estimates"],
        "semester_estimates.csv":result["semester_estimates"],
        "transitions.csv":result["transitions"],
        "choice_attribution.csv":result["attribution"],
    }
    for name,frame in frames.items():
        _write(frame,out/name)
    (out/"qa.json").write_text(json.dumps(result["qa"],indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"config.lock.json").write_text(json.dumps(cfg,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    payload=list(frames)+["qa.json","config.lock.json"]
    manifest={
        "schema":"cedlas-dt370-choice-poverty-attribution/v1",
        "artifact_type":"research.argentina-poverty-cedlas-choice-attribution/v1",
        "status":"forensic_replication_validation",
        "choice_release_id":result["qa"]["choice_release_id"],
        "choice_manifest_sha256":result["qa"]["choice_manifest_sha256"],
        "primary_engel_release_id":result["qa"]["primary_engel_release_id"],
        "primary_engel_manifest_sha256":result["qa"]["primary_engel_manifest_sha256"],
        "official_basket_release_id":result["qa"]["official_basket_release_id"],
        "paper_exact_max_abs_table5_difference_pp":result["qa"]["paper_exact_max_abs_table5_difference_pp"],
        "paper_exact_target_tolerance_pp":0.1,
        "m2_reporting_drift":"deferred",
        "nonresponse_calibration_performed":False,
        "predictive_welfare_execution_performed":False,
        "census_execution_performed":False,
        "files":{},
    }
    for name in payload:
        p=out/name
        manifest["files"][name]={"bytes":p.stat().st_size,"sha256":_sha(p)}
    seed=json.dumps({
        "choice":manifest["choice_manifest_sha256"],
        "primary_engel":manifest["primary_engel_manifest_sha256"],
        "periods":cfg["periods"],
    },sort_keys=True,separators=(",",":")).encode()
    manifest["release_id"]="cedlas-choice-poverty-"+hashlib.sha256(seed).hexdigest()[:16]
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["qa"]["status"],"release_id":manifest["release_id"],"output":str(out)},indent=2))


if __name__=="__main__":
    main()
