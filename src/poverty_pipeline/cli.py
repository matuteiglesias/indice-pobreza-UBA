"""Command line entry point for contract-only validation and synthetic QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from poverty_pipeline.adapters import adapt_census, adapt_income
from poverty_pipeline.contracts import ContractError, validate_lock
from poverty_pipeline.planning import ExecutionPlan, build_execution_plan


def _resolved_releases(lock: dict) -> dict:
    """Expose the release-resolution boundary after contract validation."""
    # validate_lock has already resolved every pin and checked its digest before
    # returning; adapters must receive only these resolved release objects.
    return lock["_validated_releases"]


def _materialize_and_qa(releases: dict, plan: ExecutionPlan) -> dict:
    """Stage 4: run the adapters and their strict cardinality/coverage QA."""
    persons, _, census_qa = adapt_census(releases["census"])
    _, income_qa = adapt_income(
        releases["income"], persons, selected_period=plan.selected_period,
        sample_id_namespace=plan.id_namespace,
        requested_output_transform=plan.approved_scientific_policies["income_output_transform"],
    )
    return {"census": census_qa, "income": income_qa}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="poverty_pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-lock")
    validate.add_argument("lock", type=Path)
    validate.add_argument("--qa-output", type=Path)
    args = parser.parse_args(argv)
    try:
        # Stage 1: validate the execution lock. validate_lock also performs the
        # content-addressed resolution required before it returns successfully.
        lock = validate_lock(args.lock)
        # Stage 2: expose only resolved and validated releases.
        releases = _resolved_releases(lock)
        # Stage 3: decide compatibility and materialization without loading rows.
        plan = build_execution_plan(lock)
        # Stage 4: adapt/materialize inputs and collect adapter QA.
        release_qa = _materialize_and_qa(releases, plan)
        # Stage 5 (scientific engine), stage 6 (aggregation), and stage 7
        # (packaging) are intentionally unreachable for contracts_only.
        qa = {
            "slice_id": lock["slice_id"], "mode": "contracts_only",
            "releases": release_qa,
            "adult_equivalence": "unresolved", "regional_baskets": "unresolved",
            "poverty_kernel_authorized": plan.kernel_authorized,
            "scientific_execution_performed": False,
            "orchestration_stopped_after": "adapter_qa",
        }
        rendered = json.dumps(qa, indent=2, sort_keys=True) + "\n"
        if args.qa_output:
            args.qa_output.parent.mkdir(parents=True, exist_ok=True)
            args.qa_output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except ContractError as exc:
        parser.exit(2, f"contract error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
