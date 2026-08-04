#!/usr/bin/env python3
"""Read-only, bounded inventory of historical poverty artifacts; never joins rows."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
paths=['data/Pobreza','data/results','data/geojson','data/yr_samples','data/Fitted_RF','/media/matias/Elements/suite/poblaciones','/media/matias/Elements/suite/out']
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def inspect(p):
 x={'path':str(p.resolve()),'sha256':digest(p),'byte_size':p.stat().st_size,'safe_to_package_without_mutation':True}
 if p.suffix.lower()=='.csv':
  try:
   with p.open(newline='',encoding='utf8',errors='replace') as f:
    r=csv.reader(f); cols=next(r,[]);n=sum(1 for _ in r)
   low=' '.join(cols).lower();x.update(columns=cols,row_count=n,inferred_entity='person' if 'person' in low or 'persona' in low else 'household' if 'hog' in low else 'aggregate_or_unknown',sample_fraction=None,period=None,id_columns=[c for c in cols if 'id' in c.lower()],id_namespace_evidence=None,income_transform_evidence='unknown',monetary_reference_evidence='unknown',stage_family='RFC4/final-income' if 'rfc4' in p.name.lower() else 'historical-output',geography_coverage='columns-only')
  except OSError:x['read_error']='unable to parse'
 return x
items=[]
for raw in paths:
 d=Path(raw) if raw.startswith('/') else ROOT/raw
 if d.exists():
  for p in sorted(d.rglob('*')):
   if p.is_file() and p.stat().st_size<50_000_000:items.append(inspect(p))
out=ROOT/'build/recovery';out.mkdir(parents=True,exist_ok=True);(out/'local-artifact-inventory.json').write_text(json.dumps({'schema_version':'local-artifact-inventory/v1','artifacts':items},indent=2,sort_keys=True)+'\n')
matched=False # proof requires explicit IDs, period, sample fraction, transform and monetary identity.
report='''# Local artifact recovery report\n\nNo demonstrably compatible Census/RFC4 final-income pair was found. Historical aggregate results and geography exist, but they do not prove an exact shared person-ID namespace, period, row coverage, transform, and monetary reference. No fuzzy or positional join was attempted.\n\n## Required producer packet\n\n**Both** a deterministic Census sample release and a Census-indexed final person-income prediction release are required, with exact IDs, sample fraction, period, transform and monetary identity declared in immutable manifests.\n\nIncomplete provenance remains a warning; incompatibility remains a hard blocker. No legacy candidate was produced.\n'''
(out/'LOCAL_ARTIFACT_RECOVERY_REPORT.md').write_text(report);print(f'inventoried {len(items)} artifacts; matched_pair={matched}')
