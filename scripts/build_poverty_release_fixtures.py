#!/usr/bin/env python3
"""Build byte-stable, explicitly synthetic producer releases and their lock."""
import csv, hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'fixtures/releases'; LOCK=ROOT/'fixtures/slice-locks/poverty-release-synthetic.json'
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
def table(p,fields,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='',encoding='utf8') as f: w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def release(name,typ,period,compat,files,limitations,upstream=()):
 d=OUT/name
 if d.exists(): shutil.rmtree(d)
 d.mkdir(parents=True)
 for role,path,schema,build in files:
  build(d/path)
 dump(d/'producer_qa.json',{'warnings':limitations,'verification':'passed'})
 entries=[]
 for role,path,schema,_ in files:
  p=d/path; entries.append({'path':path,'role':role,'schema_identity':schema,'sha256':h(p),'size':p.stat().st_size})
 q=d/'producer_qa.json'; reports=[{'path':q.name,'role':'producer_qa','schema_identity':'artifact-qa/v1','sha256':h(q),'size':q.stat().st_size}]
 m={'schema_version':'research-artifact-manifest/v1','artifact_type':typ,'release_id':name,'status':'fixture','immutable':True,'producer':{'repository':'repo.synthetic-fixtures','commit':'1'*40},'period':period,'compatibility':compat,'files':entries,'reports':reports,'limitations':limitations,'unresolved_blockers':[],'upstream_manifests':list(upstream)}
 dump(d/'manifest.json',m); return d,m,h(d/'manifest.json')
period='2024-Q1'; ns='cpv2010:poverty-visible/v1'; money='ARS-2024-Q1'
# Publish the repository method table unchanged, while declaring its exact domain.
ae=release('adult-equivalence-candidate-source-bytes-v1','research.poverty-adult-equivalence/v1','methodology-current',{'sex_codes':['1','2'],'sex_dictionary':{'1':'male','2':'female'},'age_min':0,'age_max':110,'methodology_id':'repo-adulto-eq-candidate-v1','source_sha256':h(ROOT/'data/info/adulto_eq.csv')},[('adult_equivalence','adult_equivalence.csv','adult-equivalence/v1',lambda p: shutil.copyfile(ROOT/'data/info/adulto_eq.csv',p))],['Documentary INDEC methodology/version is not proven in this repository; candidate use only.'])
persons=[('p1','h1','1',30,'r1',1),('p2','h1','2',30,'r1',1),('p3','h2','1',30,'r2',2),('p4','h3','2',30,'r3',1.5),('p5','h4','1',30,'r4',1),('p6','h5','2',30,'r5',3),('p7','h6','1',30,'r6',1),('p8','h6','2',30,'r6',1)]
hhs=[('h1','001','R1'),('h2','002','R1'),('h3','003','R2'),('h4','001','R2'),('h5','002','R1'),('h6','003','R2')]
def cp(p): table(p,['sample_person_id','sample_household_id','sex_code','age_years','radio_2010_id','sample_weight'],[dict(zip(['sample_person_id','sample_household_id','sex_code','age_years','radio_2010_id','sample_weight'],r)) for r in persons])
def ch(p): table(p,['sample_household_id','department_2010_id','region_id'],[dict(zip(['sample_household_id','department_2010_id','region_id'],r)) for r in hhs])
census=release('census-synthetic-visible-2024q1-v1','research.census-sample/v1',period,{'allowed_provenance_columns':[],'geography_vintage':'CPV-2010','household_schema':'census-household/v1','person_schema':'census-person/v1','sample_id_namespace':ns,'universe':'synthetic-residents','sampling_provenance':'synthetic-hand-calculated','projection_provenance':'none'},[('census_persons','persons.csv','census-person/v1',cp),('census_households','households.csv','census-household/v1',ch)],['Synthetic fixture; weights and records are not population estimates.'])
# Totals deliberately include below CBA, between, equality at CBT, and above CBT.
amounts=[25,25,75,120,200,300,250,250]
def inc(p):
 rows=[]
 import math
 for person,amount in zip(persons,amounts): rows.append({'sample_person_id':person[0],'period':period,'prediction_value':format(math.log10(amount),'.15g'),'prediction_transform':'log10_ars','monetary_reference':money,'classification':'synthetic','model_release_id':'synthetic-income-model-v1'})
 table(p,['sample_person_id','period','prediction_value','prediction_transform','monetary_reference','classification','model_release_id'],rows)
ups=[{'artifact_type':'research.eph-annual-input/v1','release_id':'synthetic-eph-lineage-v1','manifest_sha256':'2'*64},{'artifact_type':'research.eph-model-execution/v1','release_id':'synthetic-model-lineage-v1','manifest_sha256':'3'*64}]
income=release('income-synthetic-log10-2024q1-v1','research.person-income-predictions/v1',period,{'sample_id_namespace':ns,'prediction_schema':'person-income-predictions/v1','entity':'person','prediction_transform':'log10_ars','monetary_reference':money,'currency':'ARS','price_reference':money,'classification':'synthetic'},[('person_income_predictions','person_income.csv','person-income-predictions/v1',inc)],['Mechanical log inversion is exercised; this is not an unbiased expectation.'],ups)
def baskets(p): table(p,['region','period','cba','cbt'],[{'region':f'R{i}','period':period,'cba':100,'cbt':200} for i in range(1,7)])
basket=release('regional-baskets-synthetic-six-region-2024q1-v1','research.regional-baskets/v1',period,{'monetary_reference':money,'currency':'ARS','price_reference':money,'unit':'currency_per_adult_equivalent','regions':[f'R{i}' for i in range(1,7)],'approval_id':'synthetic-policy-only'},[('regional_baskets','baskets.csv','regional-baskets/v1',baskets)],['Synthetic thresholds; never use as official baskets.'])
geo=ROOT/'fixtures/geography/departments-synthetic.geojson';geo.parent.mkdir(parents=True,exist_ok=True)
features=[]
for i,d in enumerate(['001','002','003']):
 x=i*2;features.append({'type':'Feature','properties':{'department_id':d,'name':f'Synthetic {d}'},'geometry':{'type':'Polygon','coordinates':[[[x,0],[x+1,0],[x+1,1],[x,1],[x,0]]]}})
dump(geo,{'type':'FeatureCollection','features':features})
def pin(x,extra):
 d,m,mh=x;return {'artifact_type':m['artifact_type'],'release_id':m['release_id'],'manifest_sha256':mh,'path':'../releases/'+d.name,**extra}
lock={'schema_version':'poverty-slice-lock/v1','slice_id':'synthetic-visible-poverty-2024q1','mode':'poverty_release','selected_period':period,'geography_level':'department_2010','census':pin(census,{'sample_id_namespace':ns,'geography_vintage':'CPV-2010'}),'income':pin(income,{'sample_id_namespace':ns,'prediction_transform':'log10_ars','monetary_reference':money}),'adult_equivalence':pin(ae,{'approval_id':'candidate-method-input-for-synthetic-only'}),'regional_baskets':pin(basket,{'monetary_reference':money,'approval_id':'synthetic-policy-only'}),'geography':{'path':'../geography/departments-synthetic.geojson','id_property':'department_id'},'approved_execution_policies':{'join':'strict','income_output_transform':'linear_ars','allow_kernel':True,'threshold':{'poverty_operator':'strict_lt','indigence_operator':'inclusive_lte','approval_id':'synthetic-test-policy'},'gap':{'definition':'threshold_minus_income','approval_id':'synthetic-test-policy'},'weight':{'policy_id':'approved_household_sample_weight','approval_id':'synthetic-test-policy','permitted_estimands':['poverty_rate','indigence_rate']}},'versions':{'contracts':'v1','package':'v1'},'unresolved_methodology':[],'upstream_lineage':{'annual_eph':ups[0],'income_model_execution':ups[1]},'outputs':{'release_root':'../../build/releases','release_version':'v1','tabular_format':'csv','spatial_output':'department_2010_geojson','bundle_roles':['household_classification','person_classification','aggregates_tidy','department_summary','national_summary','release_manifest','run_qa','limitations','checksums','department_spatial']},'scientific_execution_authorized':True}
dump(LOCK,lock)
print(LOCK)
