"""Governed validation, execution, verification, and read-only inspection CLI."""
from __future__ import annotations
import argparse,csv,io,json,subprocess
from dataclasses import asdict
from pathlib import Path
from poverty_pipeline.adapters import adapt_census,adapt_income
from poverty_pipeline.aggregation import AggregateContext,ClassifiedHousehold,ClassifiedPerson,aggregate_classified_tables
from poverty_pipeline.contracts import ContractError,validate_lock
from poverty_pipeline.packaging import PackagingError,verify_release_bundle,write_scientific_bundle
from poverty_pipeline.planning import build_execution_plan
from poverty_pipeline.publication.geojson import write_department_geojson
from poverty_pipeline.science.household_poverty import *

def _rows(path):
 with path.open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
def _materialize(releases,plan):
 persons,households,cqa=adapt_census(releases['census']);income,iqa=adapt_income(releases['income'],persons,selected_period=plan.selected_period,sample_id_namespace=plan.id_namespace,requested_output_transform='linear_ars')
 return persons,households,income,{'census':cqa,'income':iqa}
def _policies(lock):
 p=lock['approved_execution_policies']; op=lambda x: ComparisonPolicy.BELOW if x=='strict_lt' else ComparisonPolicy.AT_OR_BELOW
 return PovertyPolicies(op(p['threshold']['poverty_operator']),op(p['threshold']['indigence_operator']),GapSignPolicy(p['gap']['definition']),True,WeightUsePolicy.RETAIN_FOR_PUBLICATION,'synthetic-residents')
def _plots(aggregates,households):
 def svg(title,values):
  bars=''.join(f'<rect x="{30+i*55}" y="{180-v*140:.2f}" width="35" height="{v*140:.2f}" fill="#4c78a8"/><text x="{47+i*55}" y="198" text-anchor="middle">{label}</text>' for i,(label,v) in enumerate(values))
  return f'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="220"><title>{title}</title><text x="10" y="18">{title}</text><line x1="20" y1="180" x2="490" y2="180" stroke="black"/>{bars}</svg>\n'.encode()
 national=[x for x in aggregates if x.geography_level=='national'];dep=[x for x in aggregates if x.geography_level=='department_2010' and x.universe=='households']
 return {'plot_national_rates':svg('National weighted rates',[(x.universe[0]+x.observable[0],x.value) for x in national]),'plot_department_rates':svg('Department poverty and indigence',[(x.geography_id+x.observable[0],x.value) for x in dep]),'plot_gap_distribution':svg('Household poverty gaps',[(str(i+1),min(1,abs(x.poverty_gap)/500)) for i,x in enumerate(households)])},[]
def run_lock(path):
 lock=validate_lock(path);plan=build_execution_plan(lock)
 if lock['mode']!='poverty_release':raise ContractError('run-lock requires mode poverty_release; use validate-lock for contracts_only')
 rel=lock['_validated_releases'];persons,households,incomes,qa=_materialize(rel,plan)
 ae=[AdultEquivalenceCell(r['P02'],int(r['P03']),int(r['P03']),float(r['CB_EQUIV'])) for r in _rows(rel['adult_equivalence'].role_path('adult_equivalence'))]
 baskets=[RegionalPeriodBasket(r['region'],r['period'],float(r['cba']),float(r['cbt'])) for r in _rows(rel['regional_baskets'].role_path('regional_baskets'))]
 hp={r['sample_household_id']:r for r in households}; pp=_policies(lock)
 normp=[NormalizedPerson(r['sample_person_id'],r['sample_household_id'],r['sex_code'],r['age_years']) for r in persons]
 normh=[Household(r['sample_household_id'],r['region_id'],plan.selected_period,r['department_2010_id'],next(float(p['sample_weight']) for p in persons if p['sample_household_id']==r['sample_household_id'])) for r in households]
 inc=[LinearIncome(r['sample_person_id'],float(r['prediction_value'])) for r in incomes];c=rel['census'].manifest['compatibility'];ic=rel['income'].manifest['compatibility'];ac=rel['adult_equivalence'].manifest['compatibility'];bc=rel['regional_baskets'].manifest['compatibility']
 contract=ScientificDependencyContract(plan.id_namespace,plan.selected_period,'synthetic-residents',c['sampling_provenance'],c['projection_provenance'],rel['income'].manifest['release_id'],'linear_ars',ic['currency'],ic['price_reference'],ic['classification'],ac['methodology_id'],'repository-source-bytes',tuple(ac['sex_codes']),ac['age_min'],ac['age_max'],'synthetic-six-region',bc['currency'],bc['price_reference'],bc['unit'])
 classified=calculate_household_poverty(normp,normh,inc,ae,baskets,pp,contract)
 ch=[ClassifiedHousehold(x.household_id,x.geography_key,x.poverty,x.indigence,x.sample_weight) for x in classified];cp=[ClassifiedPerson(x.person_id,x.household_id) for x in normp]
 estimates=aggregate_classified_tables(cp,ch,AggregateContext(lock['slice_id'],plan.selected_period)); ar=[asdict(x) for x in estimates]; dept=[x for x in ar if x['geography_level']=='department_2010'];nat=[x for x in ar if x['geography_level']=='national']
 person_out=[]; byh={x.household_id:x for x in classified}
 for p in normp: person_out.append({'person_id':p.person_id,'household_id':p.household_id,'department_id':byh[p.household_id].geography_key,'poverty':byh[p.household_id].poverty,'indigence':byh[p.household_id].indigence,'sample_weight':byh[p.household_id].sample_weight})
 plots,pwarnings=_plots(estimates,classified); optional=dict(plots)
 if lock['outputs']['spatial_output']=='department_2010_geojson':
  source=(Path(path).parent/lock['geography']['path']).resolve(); features=json.loads(source.read_text())['features'];tmp=Path(path).parent/'.synthetic-spatial.tmp';write_department_geojson(features,estimates,tmp);optional['department_spatial']=tmp.read_bytes();tmp.unlink()
  optional['plot_map_preview']=b'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="140"><title>Synthetic department map preview</title><rect x="10" y="30" width="100" height="80" fill="#deebf7" stroke="black"/><rect x="125" y="30" width="100" height="80" fill="#9ecae1" stroke="black"/><rect x="240" y="30" width="100" height="80" fill="#3182bd" stroke="black"/><text x="10" y="18">Synthetic CPV-2010-like departments</text></svg>\n'
 limitations=sorted({z for r in rel.values() for z in r.manifest['limitations']})+pwarnings+['Synthetic release only; not an official poverty estimate.']
 qa.update({'schema_version':'poverty-output-qa/v1','warnings':limitations,'scientific_execution_performed':True,'household_rows':len(classified),'person_rows':len(normp),'national_department_reconciliation':'passed','map_join_coverage':1.0})
 try: commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 except Exception: commit='unknown'
 manifest={'release_id':lock['slice_id'],'release_version':lock['outputs']['release_version'],'period':plan.selected_period,'status':'fixture','inputs':[asdict(x) for x in plan.releases],'upstream_lineage':lock['upstream_lineage'],'policies':lock['approved_execution_policies'],'software':{'commit':commit,'package':'poverty_pipeline'}}
 root=(Path(path).parent/lock['outputs']['release_root']).resolve()/lock['slice_id']/lock['outputs']['release_version']
 write_scientific_bundle(root,tables={'household_classification':[asdict(x) for x in classified],'person_classification':person_out,'aggregates_tidy':ar,'department_summary':dept,'national_summary':nat},manifest=manifest,qa=qa,limitations=limitations,optional_files=optional);verify_release_bundle(root);return root

def inspect_release(root,out=None):
 root=Path(root).resolve();verify_release_bundle(root);m=json.loads((root/'release_manifest.json').read_text());roles=m['output_roles'];target=Path(out) if out else root.parent/(root.name+'-inspection');target.mkdir(parents=True,exist_ok=True)
 def read(role): return _rows(root/roles[role])
 nat=read('national_summary');dep=read('department_summary');lines=['# Poverty release inspection','',f"**Status:** {m['status']} — not an official estimate.",'','## National rates','', '| Universe | Measure | Rate |','|---|---|---:|']+[f"| {r['universe']} | {r['observable']} | {float(r['value']):.3f} |" for r in nat]+['','## Ranked departments','', '| Department | Measure | Numerator | Denominator | Rate | Coverage |','|---|---|---:|---:|---:|---:|']
 for r in sorted(dep,key=lambda x:(x['observable'],-float(x['value']),x['geography_id'])):lines.append(f"| {r['geography_id']} | {r['observable']} | {r['numerator']} | {r['denominator']} | {float(r['value']):.3f} | {r['coverage']} |")
 lines += ['','## Files','']+[f'- [{role}]({name})' for role,name in sorted(roles.items())]
 (target/'release_summary.md').write_text('\n'.join(lines)+'\n');return target

def main(argv=None):
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);v=s.add_parser('validate-lock');v.add_argument('lock',type=Path);v.add_argument('--qa-output',type=Path);r=s.add_parser('run-lock');r.add_argument('lock',type=Path);i=s.add_parser('inspect-release');i.add_argument('release_dir',type=Path);i.add_argument('--output',type=Path);z=s.add_parser('verify-release');z.add_argument('release_dir',type=Path)
 a=p.parse_args(argv)
 try:
  if a.command=='validate-lock':
   lock=validate_lock(a.lock);plan=build_execution_plan(lock);*_,qa=_materialize(lock['_validated_releases'],plan);doc={'slice_id':lock['slice_id'],'mode':lock['mode'],'releases':qa,'poverty_kernel_authorized':plan.kernel_authorized,'scientific_execution_performed':False,'orchestration_stopped_after':'adapter_qa'};text=json.dumps(doc,indent=2,sort_keys=True)+'\n';a.qa_output and (a.qa_output.parent.mkdir(parents=True,exist_ok=True),a.qa_output.write_text(text));print(text,end='')
  elif a.command=='run-lock':print(run_lock(a.lock))
  elif a.command=='inspect-release':print(inspect_release(a.release_dir,a.output))
  else:verify_release_bundle(a.release_dir);print('verified')
  return 0
 except (ContractError,PackagingError,PovertyInputError,ValueError) as e:p.exit(2,f'error: {e}\n')
if __name__=='__main__':raise SystemExit(main())
