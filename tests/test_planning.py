import unittest
from types import MappingProxyType
from pathlib import Path

from poverty_pipeline.contracts import ContractError, validate_lock
from poverty_pipeline.planning import build_execution_plan


ROOT = Path(__file__).parents[1]


class PlanningTests(unittest.TestCase):
    def test_contract_plan_is_metadata_only_and_stops_at_adapter_qa(self):
        lock = validate_lock(ROOT / "fixtures/slice-locks/contracts-only.yaml")
        plan = build_execution_plan(lock)

        self.assertFalse(plan.kernel_authorized)
        self.assertEqual(
            [step.name for step in plan.materialization_steps],
            ["adapt_census", "adapt_income", "adapter_qa"],
        )
        self.assertEqual({item.input_name for item in plan.releases}, {"census", "income"})
        self.assertIsInstance(plan.approved_scientific_policies, MappingProxyType)
        self.assertFalse(hasattr(plan, "persons"))
        self.assertFalse(hasattr(plan, "households"))

    def test_unvalidated_lock_cannot_be_planned(self):
        with self.assertRaisesRegex(ContractError, "validated slice lock"):
            build_execution_plan({})


if __name__ == "__main__":
    unittest.main()
