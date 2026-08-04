#!/usr/bin/env python3
"""Report locally available governed output releases and verification status."""
import csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from poverty_pipeline.packaging import verify_release_bundle
root=Path(sys.argv[1] if len(sys.argv)>1 else 'build/releases');rows=[]
for p in sorted(root.rglob('release_manifest.json')) if root.exists() else []:
 m=json.loads(p.read_text()); ok=True
 try:verify_release_bundle(p.parent)
 except ValueError:ok=False
 lim=(p.parent/m['output_roles']['limitations']).read_text().splitlines()[2:]
 rows.append({'release_id':m['release_id'],'period':m['period'],'status':m['status'],'location':str(p.parent.resolve()),'limitations':' | '.join(x.removeprefix('- ') for x in lim),'verification_result':'passed' if ok else 'failed'})
out=Path('build/release-index');out.mkdir(parents=True,exist_ok=True);(out/'release-index.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n')
with (out/'release-index.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['release_id','period','status','location','limitations','verification_result']);w.writeheader();w.writerows(rows)
print(json.dumps(rows,indent=2))
