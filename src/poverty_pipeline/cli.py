"""Command line entry point for contract-only validation and synthetic QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from poverty_pipeline.adapters import adapt_census, adapt_income
from poverty_pipeline.contracts import ContractError, validate_lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="poverty_pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-lock")
    validate.add_argument("lock", type=Path)
    validate.add_argument("--qa-output", type=Path)
    args = parser.parse_args(argv)
    try:
        lock = validate_lock(args.lock)
        census = lock["_validated_releases"]["census"]
        income = lock["_validated_releases"]["income"]
        persons, households, census_qa = adapt_census(census)
        _, income_qa = adapt_income(
            income, persons, selected_period=lock["selected_period"],
            sample_id_namespace=lock["census"]["sample_id_namespace"],
            requested_output_transform=lock["approved_execution_policies"]["income_output_transform"],
        )
        qa = {
            "slice_id": lock["slice_id"], "mode": "contracts_only",
            "releases": {"census": census_qa, "income": income_qa},
            "adult_equivalence": "unresolved", "regional_baskets": "unresolved",
            "poverty_kernel_authorized": False, "scientific_execution_performed": False,
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

