#!/usr/bin/env python3
"""Validate and summarize the cross-ecosystem commissioning registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = Path(__file__).with_name("registry.json")
SCHEMA = "poverty-ecosystem-commissioning-registry/v1"
CLOSURE_SCHEMA = "poverty-ecosystem-commissioning-closure/v1"
STATUSES = {
    "closed_pass",
    "closed_negative",
    "diagnostic_only",
    "revalidate",
    "blocked",
    "superseded",
}
TERMINAL_STATUSES = {"closed_pass", "closed_negative", "diagnostic_only"}
STAGES = {
    "truth",
    "within_domain_model",
    "transport",
    "calibration",
    "downstream_impact",
    "observability",
}
ACCEPTANCE_STATUSES = {"accepted", "rejected", "needs_adjudication"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RegistryError(ValueError):
    pass


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA:
        raise RegistryError(f"unexpected registry schema: {data.get('schema_version')}")
    return data


def load_closure(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != CLOSURE_SCHEMA:
        raise RegistryError(f"unexpected closure schema: {data.get('schema_version')}")
    return data


def _require_text(record: dict[str, Any], key: str, context: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{context} missing nonempty {key}")


def _canonical_sha256(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _surface_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {surface["id"]: surface for surface in data["surfaces"]}


def _closure_program(data: dict[str, Any], program_id: str) -> dict[str, Any]:
    programs = data.get("closure_programs") or []
    for program in programs:
        if program.get("id") == program_id:
            return program
    raise RegistryError(f"unknown closure program: {program_id}")


def _program_contract_sha256(data: dict[str, Any], program_id: str) -> str:
    program = _closure_program(data, program_id)
    surfaces = _surface_map(data)
    required = set(program["questions"])
    frontier = list(required)
    while frontier:
        sid = frontier.pop()
        for dep in surfaces[sid]["depends_on"]:
            if dep not in required:
                required.add(dep)
                frontier.append(dep)
    payload = {
        "program": program,
        "surfaces": {
            sid: {
                "stage": surfaces[sid]["stage"],
                "authority": surfaces[sid]["authority"],
                "depends_on": surfaces[sid]["depends_on"],
                "rerun_trigger": surfaces[sid]["rerun_trigger"],
            }
            for sid in sorted(required)
        },
    }
    return _canonical_sha256(payload)


def _identity_key(record: dict[str, Any], context: str) -> tuple[str, str, str]:
    _require_text(record, "id", context)
    sha256 = record.get("sha256")
    git_commit = record.get("git_commit")
    valid_sha256 = isinstance(sha256, str) and SHA256_RE.fullmatch(sha256) is not None
    valid_git = isinstance(git_commit, str) and GIT_SHA_RE.fullmatch(git_commit) is not None
    if not valid_sha256 and not valid_git:
        raise RegistryError(f"{context} requires exact sha256 or git_commit identity")
    if sha256 is not None and not valid_sha256:
        raise RegistryError(f"{context} invalid sha256")
    if git_commit is not None and not valid_git:
        raise RegistryError(f"{context} invalid git_commit")
    if valid_sha256:
        return (record["id"], "sha256", sha256)
    return (record["id"], "git_commit", git_commit)


def _validate_evidence(evidence: Any, period: str, context: str) -> None:
    if not isinstance(evidence, list) or not evidence:
        raise RegistryError(f"{context} evidence must be a nonempty list")
    for idx, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise RegistryError(f"{context} evidence[{idx}] must be an object")
        _identity_key(item, f"{context}.evidence[{idx}]")
        if item.get("period") != period:
            raise RegistryError(
                f"{context} evidence[{idx}] period {item.get('period')!r} != {period!r}"
            )


def validate_registry(data: dict[str, Any]) -> dict[str, Any]:
    vocabulary = data.get("status_vocabulary")
    if not isinstance(vocabulary, dict) or set(vocabulary) != STATUSES:
        raise RegistryError(
            f"status vocabulary mismatch: {sorted(vocabulary or {})} != {sorted(STATUSES)}"
        )

    invariants = data.get("invariants") or {}
    if invariants.get("census_design_inverse_probability_is_analysis_weight") is not False:
        raise RegistryError("Census design inverse probability must remain non-analysis weight")
    if invariants.get("no_generic_raking_or_ipf") is not True:
        raise RegistryError("generic raking/IPF must remain disabled")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise RegistryError("registry surfaces must be a nonempty list")

    by_id: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise RegistryError("surface entry must be an object")
        sid = surface.get("id")
        if not isinstance(sid, str) or not sid:
            raise RegistryError("surface missing id")
        if sid in by_id:
            raise RegistryError(f"duplicate surface id: {sid}")
        by_id[sid] = surface

        for key in (
            "name",
            "family",
            "stage",
            "question",
            "outcome_authority",
            "entity_geography",
            "promotion_role",
            "rerun_trigger",
        ):
            _require_text(surface, key, sid)

        if surface["stage"] not in STAGES:
            raise RegistryError(f"{sid} unsupported stage: {surface['stage']}")

        authority = surface.get("authority") or {}
        _require_text(authority, "repository", f"{sid}.authority")
        _require_text(authority, "path", f"{sid}.authority")

        current = surface.get("current") or {}
        status = current.get("status")
        if status not in STATUSES - {"superseded"}:
            raise RegistryError(f"{sid} unsupported active status: {status}")
        _require_text(current, "scope", f"{sid}.current")
        evidence = current.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise RegistryError(f"{sid}.current evidence must be a nonempty string list")

        deps = surface.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
            raise RegistryError(f"{sid} depends_on must be a string list")

        if not isinstance(surface.get("weights"), dict):
            raise RegistryError(f"{sid} weights must be explicit")
        if not isinstance(surface.get("calibration"), dict):
            raise RegistryError(f"{sid} calibration must be explicit")

    missing = sorted(
        {dep for surface in surfaces for dep in surface["depends_on"] if dep not in by_id}
    )
    if missing:
        raise RegistryError(f"unknown dependencies: {missing}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(sid: str) -> None:
        if sid in visited:
            return
        if sid in visiting:
            raise RegistryError(f"dependency cycle detected at {sid}")
        visiting.add(sid)
        for dep in by_id[sid]["depends_on"]:
            visit(dep)
        visiting.remove(sid)
        visited.add(sid)

    for sid in by_id:
        visit(sid)

    programs = data.get("closure_programs")
    if not isinstance(programs, list) or not programs:
        raise RegistryError("closure_programs must be a nonempty list")
    program_ids: set[str] = set()
    for program in programs:
        if not isinstance(program, dict):
            raise RegistryError("closure program must be an object")
        for key in ("id", "period"):
            _require_text(program, key, "closure_program")
        if program["id"] in program_ids:
            raise RegistryError(f"duplicate closure program id: {program['id']}")
        program_ids.add(program["id"])
        questions = program.get("questions")
        if not isinstance(questions, list) or not questions or not all(
            isinstance(item, str) and item in by_id for item in questions
        ):
            raise RegistryError(f"{program['id']} questions must reference active surfaces")
        if len(set(questions)) != len(questions):
            raise RegistryError(f"{program['id']} contains duplicate questions")
        rules = program.get("rules") or {}
        if rules.get("l2_forbidden_features") != ["H06"]:
            raise RegistryError(f"{program['id']} must preserve the bounded H06 exclusion")
        if rules.get("l3_expected_domains") != 32:
            raise RegistryError(f"{program['id']} must preserve the 32-domain L3 contract")
        if rules.get("l4_arms") != [
            "no_labor",
            "true_labor_oracle",
            "transportable_labor_probabilities",
        ]:
            raise RegistryError(f"{program['id']} must preserve the governed L4 arms")
        shared = rules.get("l4_shared_identity_fields")
        if not isinstance(shared, list) or not shared:
            raise RegistryError(f"{program['id']} missing L4 shared identity fields")

    superseded = data.get("superseded")
    if not isinstance(superseded, list):
        raise RegistryError("superseded must be a list")
    historical_ids: set[str] = set()
    for item in superseded:
        if not isinstance(item, dict):
            raise RegistryError("superseded entry must be an object")
        _require_text(item, "id", "superseded")
        if item["id"] in historical_ids or item["id"] in by_id:
            raise RegistryError(f"duplicate historical id: {item['id']}")
        historical_ids.add(item["id"])
        if item.get("status") != "superseded":
            raise RegistryError(f"{item['id']} must have superseded status")
        _require_text(item, "replaced_by", item["id"])
        _require_text(item, "keep_for", item["id"])
        _require_text(item, "reason", item["id"])

    return {
        "schema_version": SCHEMA,
        "active_surfaces": len(by_id),
        "historical_surfaces": len(historical_ids),
        "closure_programs": len(program_ids),
        "statuses": {
            status: sum(1 for surface in surfaces if surface["current"]["status"] == status)
            for status in sorted(STATUSES - {"superseded"})
        },
    }



def build_closure_skeleton(
    registry: dict[str, Any], program_id: str
) -> dict[str, Any]:
    validate_registry(registry)
    program = _closure_program(registry, program_id)
    surfaces = _surface_map(registry)
    questions: dict[str, Any] = {}
    for sid in program["questions"]:
        surface = surfaces[sid]
        questions[sid] = {
            "period": program["period"],
            "status": surface["current"]["status"],
            "producer": {
                "repository": surface["authority"]["repository"],
                "git_commit": None,
            },
            "artifact": {"id": None, "sha256": None},
            "parents": {},
            "evidence": [],
            "acceptance": {"status": "needs_adjudication", "checks": []},
            "closure_reason": None,
            "reopen_triggers": [surface["rerun_trigger"]],
        }
    questions["L2"]["feature_contract"] = {
        "id": None,
        "sha256": None,
        "features": [],
    }
    questions["L3"]["calibration"] = {
        "domain_count": None,
        "targets": {"id": None, "sha256": None},
        "qa": {"id": None, "sha256": None},
        "gate_status": None,
    }
    questions["L4"]["comparison"] = {
        "arms": [
            {
                "name": name,
                **{field: None for field in program["rules"]["l4_shared_identity_fields"]},
            }
            for name in program["rules"]["l4_arms"]
        ],
        "adjudication": {
            "oracle_labor_useful": "needs_adjudication",
            "transportable_bridge_improves": "needs_adjudication",
        },
    }
    return {
        "schema_version": CLOSURE_SCHEMA,
        "program_id": program_id,
        "period": program["period"],
        "registry": {
            "schema_version": registry["schema_version"],
            "program_contract_sha256": _program_contract_sha256(registry, program_id),
        },
        "questions": questions,
    }


def validate_closure(
    closure: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any]:
    validate_registry(registry)
    if closure.get("schema_version") != CLOSURE_SCHEMA:
        raise RegistryError(f"unexpected closure schema: {closure.get('schema_version')}")
    program_id = closure.get("program_id")
    if not isinstance(program_id, str):
        raise RegistryError("closure missing program_id")
    program = _closure_program(registry, program_id)
    period = closure.get("period")
    if period != program["period"]:
        raise RegistryError(
            f"closure period {period!r} != program period {program['period']!r}"
        )
    registry_ref = closure.get("registry") or {}
    if registry_ref.get("schema_version") != registry["schema_version"]:
        raise RegistryError("closure registry schema does not match current registry")
    if registry_ref.get("program_contract_sha256") != _program_contract_sha256(
        registry, program_id
    ):
        raise RegistryError(
            "closure program contract fingerprint does not match current registry"
        )

    questions = closure.get("questions")
    if not isinstance(questions, dict) or set(questions) != set(program["questions"]):
        raise RegistryError("closure questions must exactly match the governed program")

    surfaces = _surface_map(registry)
    terminal: dict[str, str] = {
        sid: surfaces[sid]["current"]["status"] for sid in surfaces
    }
    for sid, record in questions.items():
        if not isinstance(record, dict):
            raise RegistryError(f"{sid} closure entry must be an object")
        status = record.get("status")
        if status not in STATUSES - {"superseded"}:
            raise RegistryError(f"{sid} unsupported closure status: {status}")
        if record.get("period") != period:
            raise RegistryError(f"{sid} evidence is for the wrong quarter")
        terminal[sid] = status

    for sid in program["questions"]:
        record = questions[sid]
        status = record["status"]
        is_terminal = status in TERMINAL_STATUSES
        acceptance = record.get("acceptance") or {}
        if acceptance.get("status") not in ACCEPTANCE_STATUSES:
            raise RegistryError(f"{sid} invalid acceptance status")
        if not isinstance(acceptance.get("checks"), list):
            raise RegistryError(f"{sid} acceptance checks must be a list")

        producer = record.get("producer") or {}
        expected_repo = surfaces[sid]["authority"]["repository"]
        if producer.get("repository") != expected_repo:
            raise RegistryError(
                f"{sid} producer repository does not match registry authority"
            )

        if is_terminal:
            git_commit = producer.get("git_commit")
            if not isinstance(git_commit, str) or GIT_SHA_RE.fullmatch(git_commit) is None:
                raise RegistryError(
                    f"{sid} terminal evidence requires exact producer git_commit"
                )
            _identity_key(record.get("artifact") or {}, f"{sid}.artifact")
            _validate_evidence(record.get("evidence"), period, sid)
            if acceptance.get("status") != "accepted":
                raise RegistryError(
                    f"{sid} terminal status requires accepted adjudication"
                )
            _require_text(record, "closure_reason", sid)
            triggers = record.get("reopen_triggers")
            if triggers != [surfaces[sid]["rerun_trigger"]]:
                raise RegistryError(
                    f"{sid} reopening trigger must match the registry authority"
                )

            parents = record.get("parents")
            if not isinstance(parents, dict):
                raise RegistryError(f"{sid} parents must be explicit")
            expected_deps = surfaces[sid]["depends_on"]
            if set(parents) != set(expected_deps):
                raise RegistryError(
                    f"{sid} parent identities must exactly match dependencies"
                )
            for dep in expected_deps:
                parent = parents[dep]
                if not isinstance(parent, dict):
                    raise RegistryError(f"{sid}.parents.{dep} must be an object")
                if parent.get("period") != period:
                    raise RegistryError(f"{sid}.parents.{dep} period mismatch")
                _identity_key(parent, f"{sid}.parents.{dep}")
                if terminal[dep] not in TERMINAL_STATUSES:
                    raise RegistryError(
                        f"{sid} cannot close while parent {dep} is {terminal[dep]}"
                    )
                if dep in questions:
                    expected = _identity_key(
                        questions[dep].get("artifact") or {}, f"{dep}.artifact"
                    )
                    actual = _identity_key(parent, f"{sid}.parents.{dep}")
                    if actual != expected:
                        raise RegistryError(
                            f"{sid} parent {dep} does not match closure artifact"
                        )

    l2 = questions.get("L2")
    if l2 and l2["status"] in TERMINAL_STATUSES:
        contract = l2.get("feature_contract") or {}
        _identity_key(contract, "L2.feature_contract")
        features = contract.get("features")
        if not isinstance(features, list) or not all(
            isinstance(x, str) for x in features
        ):
            raise RegistryError("L2.feature_contract features must be a string list")
        forbidden = {
            x.upper() for x in program["rules"]["l2_forbidden_features"]
        }
        present = forbidden.intersection(x.upper() for x in features)
        if present:
            raise RegistryError(
                f"L2 forbidden features remain in contract: {sorted(present)}"
            )

    l3 = questions.get("L3")
    if l3 and l3["status"] in TERMINAL_STATUSES:
        calibration = l3.get("calibration") or {}
        expected_domains = program["rules"]["l3_expected_domains"]
        if calibration.get("domain_count") != expected_domains:
            raise RegistryError(
                f"L3 domain_count {calibration.get('domain_count')} != {expected_domains}"
            )
        _identity_key(
            calibration.get("targets") or {}, "L3.calibration.targets"
        )
        _identity_key(calibration.get("qa") or {}, "L3.calibration.qa")
        if calibration.get("gate_status") != "PASS":
            raise RegistryError(
                "L3 terminal closure requires existing calibration gate PASS"
            )

    l4 = questions.get("L4")
    if l4 and l4["status"] in TERMINAL_STATUSES:
        comparison = l4.get("comparison") or {}
        arms = comparison.get("arms")
        if not isinstance(arms, list):
            raise RegistryError("L4 comparison arms must be a list")
        expected_names = program["rules"]["l4_arms"]
        if [arm.get("name") for arm in arms if isinstance(arm, dict)] != expected_names:
            raise RegistryError(
                "L4 comparison must contain the governed three arms in order"
            )
        shared_fields = program["rules"]["l4_shared_identity_fields"]
        for field in shared_fields:
            values: list[str] = []
            for arm in arms:
                value = arm.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise RegistryError(
                        f"L4 arm {arm.get('name')} missing {field}"
                    )
                if field.endswith("sha256") and SHA256_RE.fullmatch(value) is None:
                    raise RegistryError(
                        f"L4 arm {arm.get('name')} invalid {field}"
                    )
                values.append(value)
            if len(set(values)) != 1:
                raise RegistryError(
                    f"L4 arms differ on governed identity field {field}"
                )
        adjudication = comparison.get("adjudication") or {}
        for key in ("oracle_labor_useful", "transportable_bridge_improves"):
            if adjudication.get(key) not in {"yes", "no", "needs_adjudication"}:
                raise RegistryError(f"L4 invalid adjudication field {key}")
        if l4["status"] == "closed_negative":
            if (
                adjudication.get("oracle_labor_useful") != "yes"
                or adjudication.get("transportable_bridge_improves") != "no"
            ):
                raise RegistryError(
                    "L4 closed_negative requires explicit oracle=yes and "
                    "transportable_bridge=no adjudication"
                )

    statuses = {
        sid: questions[sid]["status"] for sid in program["questions"]
    }
    return {
        "schema_version": CLOSURE_SCHEMA,
        "program_id": program_id,
        "period": period,
        "statuses": statuses,
        "all_terminal": all(
            status in TERMINAL_STATUSES for status in statuses.values()
        ),
    }

def render_summary(data: dict[str, Any]) -> str:
    lines = [
        "# Commissioning registry",
        "",
        f"As of: {data['as_of']}",
        "",
        "| ID | Stage | Current status | Scope |",
        "|---|---|---|---|",
    ]
    for surface in data["surfaces"]:
        current = surface["current"]
        lines.append(
            f"| {surface['id']} | {surface['stage']} | {current['status']} | {current['scope']} |"
        )
    if data.get("superseded"):
        lines.extend(["", "## Superseded / historical"])
        for item in data["superseded"]:
            lines.append(
                f"- **{item['id']}** → {item['replaced_by']}: {item['keep_for']}."
            )
    return "\n".join(lines) + "\n"



def render_closure(closure: dict[str, Any], registry: dict[str, Any]) -> str:
    result = validate_closure(closure, registry)
    lines = [
        f"# Commissioning closure — {result['period']}",
        "",
        f"Program: `{result['program_id']}`",
        "",
        "| Question | Status | Acceptance | Evidence items |",
        "|---|---|---|---:|",
    ]
    for sid in _closure_program(registry, result["program_id"])["questions"]:
        record = closure["questions"][sid]
        lines.append(
            f"| {sid} | {record['status']} | "
            f"{record['acceptance']['status']} | {len(record['evidence'])} |"
        )
    lines.extend(
        ["", f"All terminal: `{str(result['all_terminal']).lower()}`", ""]
    )
    return "\n".join(lines)

def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    out.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    group = out.add_mutually_exclusive_group()
    group.add_argument("--summary", action="store_true")
    group.add_argument("--init-closure", metavar="PROGRAM_ID")
    group.add_argument("--validate-closure", type=Path, metavar="PATH")
    group.add_argument("--render-closure", type=Path, metavar="PATH")
    out.add_argument("--output", type=Path)
    return out


def main() -> int:
    args = parser().parse_args()
    registry = load_registry(args.registry)
    result = validate_registry(registry)
    if args.summary:
        print(render_summary(registry), end="")
    elif args.init_closure:
        if args.output is None:
            raise SystemExit("--init-closure requires --output")
        payload = build_closure_skeleton(registry, args.init_closure)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        print(args.output)
    elif args.validate_closure:
        closure = load_closure(args.validate_closure)
        print(json.dumps(validate_closure(closure, registry), sort_keys=True))
    elif args.render_closure:
        closure = load_closure(args.render_closure)
        print(render_closure(closure, registry), end="")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
