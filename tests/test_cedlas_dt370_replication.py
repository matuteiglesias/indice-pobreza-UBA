import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from science.measurement_alignment.cedlas_dt370 import run_cedlas_poverty_replication

REGIONS=("gran_buenos_aires","pampeana","noreste","noroeste","cuyo","patagonia")


def _artifact(root: Path) -> Path:
    root.mkdir(parents=True)
    rows=[]
    for month,official in zip(pd.date_range("2024-01-01","2024-06-01",freq="MS"),(100,120,140,160,180,200)):
        for region in REGIONS:
            rows.append({
                "period":month.strftime("%Y-%m-%d"),"region_id":region,
                "CBA_official":official/2,"CBT_official":official,
                "ICE_official":2,"ICE_cedlas":2.4,"CBT_cedlas":official*1.2,
            })
    pd.DataFrame(rows).to_csv(root/"threshold_paths.csv",index=False)
    (root/"manifest.json").write_text(json.dumps({
        "artifact_type":"research.argentina-regional-baskets-cedlas-dt370-replication/v1",
        "method_id":"research.argentina-regional-baskets-cedlas-dt370/published-low-education-v1",
        "release_id":"cedlas-synthetic",
        "scientific_poverty_execution_performed":False,
        "coicop02_food_fraction":"1",
        "tobacco_in_food":True,
        "regionalization":"paper_published_ratio",
        "official_basket_release_id":"basket-synthetic",
    }))
    return root


def _hh(path: Path, period: str, line: float, incomes, weights) -> Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,(income,w) in enumerate(zip(incomes,weights),1):
        rows.append({
            "period":period,"household_id":f"{period}:h{i}","basket_region":"gran_buenos_aires",
            "adult_equivalents":1.0,"ITF":income,"PONDIH":w,"member_count_records":1,
            "cba_per_ae":line/2,"cbt_per_ae":line,
        })
    pd.DataFrame(rows).to_parquet(path,index=False)
    return path


class CedlasPovertyReplicationTests(unittest.TestCase):
    def test_replication_reuses_telescope_and_pools_semester(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            art=_artifact(root/"artifact")
            q1=_hh(root/"q1"/"households.parquet","2024-Q1",120,[115,150],[1,1])
            q2=_hh(root/"q2"/"households.parquet","2024-Q2",180,[170,250],[9,1])
            # Candidate poverty: q1 first poor; q2 first poor, second nonpoor => pooled 10/12.
            targets=root/"targets.csv"
            pd.DataFrame([{
                "semester":"2024-S1","updated_consumption_person_poverty":10/12
            }]).to_csv(targets,index=False)
            result=run_cedlas_poverty_replication({
                "cedlas_replication_release":str(art),
                "external_targets":str(targets),
                "periods":[
                    {"period":"2024-Q1","telescope_a_households":str(q1)},
                    {"period":"2024-Q2","telescope_a_households":str(q2)},
                ]
            })
            self.assertEqual(result["qa"]["telescope_a_baseline_reproduction"],"pass")
            self.assertTrue(result["qa"]["all_published_semesters_within_tolerance"])
            sem=result["semester_estimates"]
            row=sem[
                (sem.period=="2024-S1")&(sem.policy=="cedlas_updated_consumption")&
                (sem.geography_level=="national")&(sem.universe=="persons")&
                (sem.concept=="poverty")&(sem.estimand=="fgt0")
            ].iloc[0]
            self.assertAlmostEqual(float(row.estimate),10/12)
            self.assertFalse(result["qa"]["welfare_changed"])
            self.assertFalse(result["qa"]["cba_changed"])


if __name__=="__main__":
    unittest.main()
