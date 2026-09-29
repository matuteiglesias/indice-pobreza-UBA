#!/usr/bin/env python3
"""Build a deterministic observed-EPH M1/M3 measurement-alignment artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .core import AlignmentError, run_alignment


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    if frame.empty:
        path.write_text("",encoding="utf-8")
    else:
        frame.to_csv(path,index=False)


def main() -> None:
    ap=argparse.ArgumentParser(description="Observed-EPH Measurement Alignment M1 timing + M3 ENGHo")
    ap.add_argument("--config",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()

    config=json.loads(args.config.read_text(encoding="utf-8"))
    result=run_alignment(config)
    out=args.output.expanduser().resolve()
    out.mkdir(parents=True,exist_ok=True)

    files={
        "quarterly_estimates.csv":result["quarterly_estimates"],
        "semester_estimates.csv":result["semester_estimates"],
        "transitions.csv":result["transitions"],
        "line_policies.csv":result["line_policies"],
        "external_comparison.csv":result["external_comparison"],
    }
    for name,frame in files.items():
        _write_frame(frame,out/name)

    (out/"qa.json").write_text(json.dumps(result["qa"],indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"config.lock.json").write_text(json.dumps(config,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    limitations="""# Limitations

Research validation only; not official INDEC statistics.

M1 is a quarter-native timing sensitivity because the governed Telescope-A surface does not identify the exact household income receipt/spending month. T1 shifts every monthly threshold one month backward and Tm averages current and lagged quarter means.

M3 consumes the signed-sales ENGHo/Engel Artifact B. It keeps observed ITF, PONDIH, adult equivalence and official CBA fixed and changes only CBT according to the named Artifact-B path.

CEDLAS values are external validation/falsification evidence only. They are not estimator inputs and exact equality is not required because reference-population and timing constructions differ.

M2 reporting drift and income non-response calibration are explicitly out of scope. No Census, province/department or Atlas computation occurs.
"""
    (out/"LIMITATIONS.md").write_text(limitations,encoding="utf-8")

    payloads=list(files)+["qa.json","config.lock.json","LIMITATIONS.md"]
    manifest={
        "schema":"measurement-alignment-artifact/v1",
        "artifact_type":"research.argentina-poverty-measurement-alignment/v1",
        "status":"candidate_diagnostic",
        "experiments":["M1_timing","M3_engho_engel"],
        "m2_reporting_drift":"deferred",
        "nonresponse_calibration_performed":False,
        "period_count":len(config["periods"]),
        "official_basket_release_id":result["qa"]["official_basket_release_id"],
        "official_basket_manifest_sha256":result["qa"]["official_basket_manifest_sha256"],
        "engel_sensitivity_release_id":result["qa"]["engel_sensitivity_release_id"],
        "engel_sensitivity_manifest_sha256":result["qa"]["engel_sensitivity_manifest_sha256"],
        "engel_reference_release_id":result["qa"]["engel_reference_release_id"],
        "engel_reference_method_id":result["qa"]["engel_reference_method_id"],
        "telescope_a_baseline_reproduction":result["qa"]["telescope_a_baseline_reproduction"],
        "scientific_poverty_execution_performed":True,
        "predictive_welfare_execution_performed":False,
        "census_execution_performed":False,
        "files":{},
    }
    for name in payloads:
        path=out/name
        manifest["files"][name]={"bytes":path.stat().st_size,"sha256":_sha256(path)}
    seed=json.dumps({
        "artifact_type":manifest["artifact_type"],
        "official_basket":manifest["official_basket_manifest_sha256"],
        "engel":manifest["engel_sensitivity_manifest_sha256"],
        "periods":config["periods"],
    },sort_keys=True,separators=(",",":")).encode()
    manifest["release_id"]="measurement-alignment-"+hashlib.sha256(seed).hexdigest()[:16]
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    print(json.dumps({
        "status":"PASS",
        "release_id":manifest["release_id"],
        "periods":manifest["period_count"],
        "output":str(out),
        "experiments":manifest["experiments"],
    },indent=2))


if __name__=="__main__":
    main()
