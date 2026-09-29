import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from science.measurement_alignment.cedlas_choice_attribution import run_cedlas_choice_attribution

REGIONS=("gran_buenos_aires","pampeana","noreste","noroeste","cuyo","patagonia")


def _choice(root: Path) -> Path:
    root.mkdir(parents=True)
    rows=[]
    variants=[
        ("paper_exact","published_equal_group","inherited_old_ice_ratio","1","1.20"),
        ("paper_vector_alcohol_only","published_equal_group","inherited_old_ice_ratio","0.7","1.15"),
    ]
    for month,official in zip(pd.date_range("2024-01-01","2024-06-01",freq="MS"),(100,120,140,160,180,200)):
        for region in REGIONS:
            for vid,ref,regionalization,factor,mult in variants:
                rows.append({
                    "variant_id":vid,"period":month.strftime("%Y-%m-%d"),"region_id":region,
                    "CBA_official":official/2,"CBT_official":official,
                    "ICE_variant":2*float(mult),"CBT_variant":official*float(mult),
                    "threshold_ratio":mult,"total_price_relative":"1","food_price_relative":"1",
                    "reference_population_structure":ref,"regionalization":regionalization,
                    "coicop02_food_fraction":factor,
                })
    pd.DataFrame(rows).to_csv(root/"threshold_paths.csv",index=False)
    pd.DataFrame([{
        "variant_id":v[0],"reference_population_structure":v[1],
        "regionalization":v[2],"coicop02_food_fraction":v[3],
    } for v in variants]).to_csv(root/"variants.csv",index=False)
    (root/"manifest.json").write_text(json.dumps({
        "artifact_type":"research.argentina-regional-baskets-cedlas-choice-attribution/v1",
        "method_id":"research.argentina-regional-baskets-cedlas-choice-attribution/v1",
        "release_id":"choice-synthetic",
        "basket_release_id":"basket-synthetic",
        "scientific_poverty_execution_performed":False,
    }))
    return root


def _primary(root: Path) -> Path:
    root.mkdir(parents=True)
    rows=[]
    for month,official in zip(pd.date_range("2024-01-01","2024-06-01",freq="MS"),(100,120,140,160,180,200)):
        for region in REGIONS:
            rows.append({
                "period":month.strftime("%Y-%m-%d"),"region_id":region,
                "CBA_official":official/2,"CBT_official":official,
                "ICE_engho17":"2.6","CBT_engho17":official*1.30,
                "level_factor":"1.3","trajectory_factor":"1","full_factor":"1.3",
                "CBT_level_only":official*1.30,"CBT_level_plus_trajectory":official*1.30,
                "food_price_relative":"1","total_expenditure_price_relative":"1",
                "food_share_engho17":"0.3846153846",
            })
    pd.DataFrame(rows).to_csv(root/"threshold_paths.csv",index=False)
    (root/"manifest.json").write_text(json.dumps({
        "artifact_type":"research.argentina-regional-baskets-engel-sensitivity/v1",
        "method_id":"research.argentina-regional-baskets-engel-sensitivity/engho17-fixed-base-regional-ipc-v1",
        "release_id":"primary-synthetic",
        "official_basket_release_id":"basket-synthetic",
        "engho_reference_release_id":"reference-synthetic",
        "scientific_poverty_execution_performed":False,
    }))
    (root/"parent_locks.json").write_text(json.dumps({
        "engho_reference":{
            "release_id":"reference-synthetic",
            "method_id":"research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2",
        }
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


class CedlasChoicePovertyTests(unittest.TestCase):
    def test_choice_variants_and_primary_p29_bridge_share_same_telescope_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            choice=_choice(root/"choice")
            primary=_primary(root/"primary")
            q1=_hh(root/"q1"/"households.parquet","2024-Q1",120,[115,150],[1,1])
            q2=_hh(root/"q2"/"households.parquet","2024-Q2",180,[170,250],[9,1])
            targets=root/"targets.csv"
            # Paper-exact thresholds are 20% higher: pooled poor mass 11/12.
            pd.DataFrame([{
                "semester":"2024-S1","updated_consumption_person_poverty":11/12,
            }]).to_csv(targets,index=False)

            result=run_cedlas_choice_attribution({
                "cedlas_choice_release":str(choice),
                "primary_engel_sensitivity_release":str(primary),
                "external_targets":str(targets),
                "periods":[
                    {"period":"2024-Q1","telescope_a_households":str(q1)},
                    {"period":"2024-Q2","telescope_a_households":str(q2)},
                ],
            })
            self.assertEqual(result["qa"]["telescope_a_baseline_reproduction"],"pass")
            self.assertTrue(result["qa"]["paper_exact_max_abs_table5_difference_pp"]<=0.1)
            self.assertFalse(result["qa"]["welfare_changed"])
            self.assertFalse(result["qa"]["cba_changed"])

            table=result["attribution"]
            self.assertEqual(
                set(table["variant_id"]),
                {"paper_exact","paper_vector_alcohol_only"},
            )
            paper=table[table["variant_id"]=="paper_exact"].iloc[0]
            alcohol=table[table["variant_id"]=="paper_vector_alcohol_only"].iloc[0]
            self.assertAlmostEqual(float(paper["person_poverty"]),11/12)
            self.assertLess(float(alcohol["person_poverty"]),float(paper["person_poverty"]))
            self.assertLess(float(paper["delta_vs_primary_p29_p48_pp"]),0)

            sem=result["semester_estimates"]
            primary_row=sem[
                (sem.period=="2024-S1")&
                (sem.policy=="primary_p29_p48_full")&
                (sem.geography_level=="national")&
                (sem.universe=="persons")&
                (sem.concept=="poverty")&
                (sem.estimand=="fgt0")
            ].iloc[0]
            self.assertGreater(float(primary_row.estimate),float(paper["person_poverty"]))


if __name__=="__main__":
    unittest.main()
