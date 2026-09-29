from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from science.measurement_alignment.core import AlignmentError, run_alignment
from science.measurement_alignment.contracts import REGIONS


def _write_basket(root: Path) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    months=pd.date_range("2023-12-01","2024-06-01",freq="MS")
    values=[80,100,120,140,160,180,200]
    rows=[]
    for region_i,region in enumerate(REGIONS):
        for period,cbt in zip(months,values):
            offset=region_i*2
            rows.append({
                "period":period.strftime("%Y-%m-%d"),
                "region_id":region,
                "CBA_nominal":str((cbt+offset)/2),
                "CBT_nominal":str(cbt+offset),
            })
    pd.DataFrame(rows).to_csv(root/"observed_nominal_monthly.csv",index=False)
    (root/"manifest.json").write_text(json.dumps({
        "artifact_type":"research.argentina-regional-baskets/v1",
        "method_id":"research.argentina-regional-baskets/source-observed-plus-price-consensus-v2",
        "release_id":"basket-synthetic",
    }))
    return root


def _write_engel(root: Path, *, signed: bool=True) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    months=pd.date_range("2024-01-01","2024-06-01",freq="MS")
    current=[100,120,140,160,180,200]
    rows=[]
    for region_i,region in enumerate(REGIONS):
        for period,cbt in zip(months,current):
            official=cbt+region_i*2
            rows.append({
                "period":period.strftime("%Y-%m-%d"),
                "region_id":region,
                "CBA_official":str(official/2),
                "CBT_official":str(official),
                "CBT_level_only":str(official*1.2),
                "CBT_level_plus_trajectory":str(official*1.3),
            })
    pd.DataFrame(rows).to_csv(root/"threshold_paths.csv",index=False)
    (root/"manifest.json").write_text(json.dumps({
        "artifact_type":"research.argentina-regional-baskets-engel-sensitivity/v1",
        "method_id":"research.argentina-regional-baskets-engel-sensitivity/engho17-fixed-base-regional-ipc-v1",
        "release_id":"engel-synthetic",
        "engho_reference_release_id":"reference-synthetic",
    }))
    (root/"parent_locks.json").write_text(json.dumps({
        "engho_reference":{
            "release_id":"reference-synthetic",
            "method_id":(
                "research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2"
                if signed else
                "research.argentina-engel-reference-structure/engho-2017-18-p29-p48-v1"
            )
        }
    }))
    return root


def _write_telescope(root: Path, period: str, *, q2: bool=False) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    cbt=120.0 if not q2 else 180.0
    cba=cbt/2
    if not q2:
        frame=pd.DataFrame([
            {"period":period,"household_id":f"{period}:h1","basket_region":"gran_buenos_aires","adult_equivalents":1.0,"ITF":115.0,"PONDIH":1.0,"member_count_records":1,"cba_per_ae":cba,"cbt_per_ae":cbt},
            {"period":period,"household_id":f"{period}:h2","basket_region":"gran_buenos_aires","adult_equivalents":1.0,"ITF":150.0,"PONDIH":1.0,"member_count_records":2,"cba_per_ae":cba,"cbt_per_ae":cbt},
        ])
    else:
        frame=pd.DataFrame([
            {"period":period,"household_id":f"{period}:h1","basket_region":"gran_buenos_aires","adult_equivalents":1.0,"ITF":190.0,"PONDIH":9.0,"member_count_records":1,"cba_per_ae":cba,"cbt_per_ae":cbt},
            {"period":period,"household_id":f"{period}:h2","basket_region":"gran_buenos_aires","adult_equivalents":1.0,"ITF":250.0,"PONDIH":1.0,"member_count_records":1,"cba_per_ae":cba,"cbt_per_ae":cbt},
        ])
    path=root/"households.parquet"
    frame.to_parquet(path,index=False)
    return path


class MeasurementAlignmentTests(unittest.TestCase):
    def test_m1_m3_and_semester_pooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            basket=_write_basket(root/"basket")
            engel=_write_engel(root/"engel")
            q1=_write_telescope(root/"q1","2024-Q1")
            q2=_write_telescope(root/"q2","2024-Q2",q2=True)
            result=run_alignment({
                "official_basket_release":str(basket),
                "engel_sensitivity_release":str(engel),
                "periods":[
                    {"period":"2024-Q1","telescope_a_households":str(q1)},
                    {"period":"2024-Q2","telescope_a_households":str(q2)},
                ],
            })
            self.assertEqual(result["qa"]["telescope_a_baseline_reproduction"],"pass")
            self.assertFalse(result["qa"]["m1_welfare_changed"])
            self.assertFalse(result["qa"]["m3_welfare_changed"])
            self.assertFalse(result["qa"]["nonresponse_calibration_performed"])

            q=result["quarterly_estimates"]
            def est(period,experiment,policy):
                row=q[
                    (q.period==period)&(q.experiment==experiment)&(q.policy==policy)&
                    (q.geography_level=="national")&(q.universe=="households")&
                    (q.concept=="poverty")&(q.estimand=="fgt0")
                ]
                return float(row.iloc[0].estimate)
            self.assertEqual(est("2024-Q1","M1","T0_current_quarter_mean"),0.5)
            self.assertEqual(est("2024-Q1","M1","T1_previous_month"),0.0)
            self.assertEqual(est("2024-Q1","M3","official"),0.5)
            self.assertEqual(est("2024-Q1","M3","engho17_level_plus_trajectory"),1.0)

            sem=result["semester_estimates"]
            pooled=sem[
                (sem.period=="2024-S1")&(sem.experiment=="M1")&
                (sem.policy=="T0_current_quarter_mean")&
                (sem.geography_level=="national")&(sem.universe=="households")&
                (sem.concept=="poverty")&(sem.estimand=="fgt0")
            ].iloc[0]
            self.assertAlmostEqual(float(pooled.estimate),1/12)
            self.assertNotAlmostEqual(float(pooled.estimate),(0.5+0.0)/2)

            transitions=result["transitions"]
            q1lag=transitions[
                (transitions.period=="2024-Q1")&
                (transitions.experiment=="M1")&
                (transitions.policy=="T1_previous_month")&
                (transitions.concept=="poverty")
            ]
            self.assertEqual(int(q1lag[q1lag.transition=="true_to_false"].iloc[0].households),1)

    def test_m3_requires_signed_sales_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            basket=_write_basket(root/"basket")
            engel=_write_engel(root/"engel",signed=False)
            q1=_write_telescope(root/"q1","2024-Q1")
            with self.assertRaisesRegex(AlignmentError,"signed-sales"):
                run_alignment({
                    "official_basket_release":str(basket),
                    "engel_sensitivity_release":str(engel),
                    "periods":[{"period":"2024-Q1","telescope_a_households":str(q1)}],
                })

    def test_t0_fails_if_telescope_parent_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            basket=_write_basket(root/"basket")
            engel=_write_engel(root/"engel")
            q1=_write_telescope(root/"q1","2024-Q1")
            frame=pd.read_parquet(q1)
            frame["cbt_per_ae"]=999
            frame.to_parquet(q1,index=False)
            with self.assertRaisesRegex(AlignmentError,"T0 does not reproduce"):
                run_alignment({
                    "official_basket_release":str(basket),
                    "engel_sensitivity_release":str(engel),
                    "periods":[{"period":"2024-Q1","telescope_a_households":str(q1)}],
                })


if __name__=="__main__":
    unittest.main()
