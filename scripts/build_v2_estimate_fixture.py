#!/usr/bin/env python3
"""Build one deterministic synthetic Poverty Estimation v2 release."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from poverty_pipeline.contracts_v2 import (
    PopulationFrameHousehold,
    PopulationFramePerson,
    PopulationFrameRelease,
    PovertyLine,
    PovertyLineRelease,
    ThresholdAreaBinding,
    ThresholdAreaBindingRelease,
    WelfareEstimate,
    WelfareRelease,
    prepare_measurement_inputs,
)
from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    HouseholdDomain,
    HouseholdWeight,
    estimate_poverty,
)
from poverty_pipeline.release_v2 import ParentReleaseRef, write_estimate_release
from poverty_pipeline.science import load_poverty_method, measure_poverty


def content_hash(value: object) -> str:
    payload = json.dumps(asdict(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def build(output: Path) -> Path:
    method_path = Path("configs/poverty_methods/indec-line-poverty-2016-v1.json")
    method = load_poverty_method(method_path)
    frame = PopulationFrameRelease(
        "frame-fixture-v2", "cpv2010:fixture-v2", "2010",
        "deterministic-household-hash-v1", "cpv2010_frame_inverse_probability",
        persons=(
            PopulationFramePerson("p1", "h1", "male", 35, "020010101", "02001", "02"),
            PopulationFramePerson("p2", "h1", "female", 34, "020010101", "02001", "02"),
            PopulationFramePerson("p3", "h2", "female", 76, "020010102", "02001", "02"),
            PopulationFramePerson("p4", "h3", "male", 10, "060140101", "06014", "06"),
        ),
        households=(
            PopulationFrameHousehold("h1", "02001", "02", 0.10, 10.0),
            PopulationFrameHousehold("h2", "02001", "02", 0.20, 5.0),
            PopulationFrameHousehold("h3", "06014", "06", 0.25, 4.0),
        ),
    )
    welfare = WelfareRelease(
        "welfare-fixture-v2", frame.namespace, "2024-Q1", "ARS", "2024-Q1-current",
        "household_total_family_income",
        (WelfareEstimate("h1", 260.0), WelfareEstimate("h2", 75.0), WelfareEstimate("h3", 100.0)),
    )
    lines = PovertyLineRelease(
        "lines-fixture-v2", "2024-Q1", "ARS", "2024-Q1-current", method.release_id,
        (PovertyLine("gba", 100.0, 180.0), PovertyLine("pampeana", 90.0, 160.0)),
    )
    binding = ThresholdAreaBindingRelease(
        "threshold-binding-fixture-v2", "department_2010",
        (
            ThresholdAreaBinding("department_2010", "02001", "gba"),
            ThresholdAreaBinding("department_2010", "06014", "pampeana"),
        ),
    )
    prepared = prepare_measurement_inputs(
        frame, welfare, lines, binding, method, estimation_period="2024-Q1"
    )
    measurement = measure_poverty(
        prepared.persons, prepared.household_welfare, prepared.household_lines, method
    )
    design = EstimationDesign(
        "cpv2010-frame-ipw-fixture", frame.weight_semantics,
        tuple(HouseholdWeight(h.household_id, h.analysis_weight) for h in frame.households),
    )
    domains = tuple(HouseholdDomain(h.household_id, "department_2010", h.department_2010_id)
                    for h in frame.households)
    estimation = estimate_poverty(
        measurement,
        domains,
        design,
        EstimationContext("poverty-estimate-fixture-v2", "2024-Q1", frame.frame_vintage),
    )
    method_hash = hashlib.sha256(method_path.read_bytes()).hexdigest()
    parents = (
        ParentReleaseRef("population_frame", frame.release_id, content_hash(frame)),
        ParentReleaseRef("welfare", welfare.release_id, content_hash(welfare)),
        ParentReleaseRef("poverty_lines", lines.release_id, content_hash(lines)),
        ParentReleaseRef("threshold_area_binding", binding.release_id, content_hash(binding)),
        ParentReleaseRef("poverty_method", method.release_id, method_hash),
    )
    return write_estimate_release(output, estimation, parents=parents, method_release_id=method.release_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/v2/poverty-estimate-fixture-v2"))
    args = parser.parse_args()
    build(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
