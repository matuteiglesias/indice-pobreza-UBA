import json, shutil, tempfile, unittest
from pathlib import Path
from poverty_pipeline.cli import run_lock
from poverty_pipeline.contracts import validate_lock
from poverty_pipeline.packaging import PackagingError, verify_release_bundle
ROOT=Path(__file__).resolve().parents[1]
class ReleaseExecutionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lock=ROOT/'fixtures/slice-locks/poverty-release-synthetic.json'; cls.out=ROOT/'build/releases/synthetic-visible-poverty-2024q1/v1';shutil.rmtree(cls.out.parent,ignore_errors=True);run_lock(cls.lock)
 def test_runtime_accepts_four_pins(self): self.assertEqual(set(validate_lock(self.lock)['_validated_releases']),{'census','income','adult_equivalence','regional_baskets'})
 def test_roles_and_visible_outputs(self):
  m=json.loads((self.out/'release_manifest.json').read_text());self.assertTrue({'household_classification','person_classification','aggregates_tidy','department_summary','national_summary','department_spatial','plot_national_rates','plot_department_rates','plot_gap_distribution'} <= set(m['output_roles']))
 def test_immutable_and_tamper_detection(self):
  with self.assertRaises(PackagingError):run_lock(self.lock)
  p=self.out/'national_summary.csv'; original=p.read_bytes();p.write_bytes(original+b'x')
  with self.assertRaises(PackagingError):verify_release_bundle(self.out)
  p.write_bytes(original);verify_release_bundle(self.out)
if __name__=='__main__':unittest.main()
