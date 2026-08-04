"""Pure planning for a validated poverty execution slice.

This module deliberately deals only in contract metadata.  In particular, plan
construction never opens a tabular file and never calls the scientific kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from poverty_pipeline.contracts import ContractError, ValidatedRelease


def _freeze(value: Any) -> Any:
    """Return a recursively immutable copy of JSON-compatible metadata."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ReleaseIdentity:
    """Resolved identity of one direct, content-addressed input release."""

    input_name: str
    artifact_type: str
    release_id: str
    manifest_sha256: str


@dataclass(frozen=True)
class DirectInputRole:
    """A file role authorized for materialization, without its file contents."""

    input_name: str
    role: str
    schema_identity: Any
    sha256: str


@dataclass(frozen=True)
class MaterializationStep:
    """An ordered orchestration boundary; this is a description, not execution."""

    name: str
    input_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable compatibility decision produced before scientific data is read."""

    slice_id: str
    mode: str
    releases: tuple[ReleaseIdentity, ...]
    selected_period: str
    id_namespace: str
    geography_vintage: str
    monetary_reference: str
    direct_input_roles: tuple[DirectInputRole, ...]
    approved_scientific_policies: Mapping[str, Any]
    requested_outputs: Mapping[str, Any]
    materialization_steps: tuple[MaterializationStep, ...]
    kernel_authorized: bool


def build_execution_plan(validated_lock: Mapping[str, Any]) -> ExecutionPlan:
    """Build an immutable plan from a lock already accepted by ``validate_lock``.

    Only manifest metadata is copied into the result.  Keeping release objects
    (which contain local paths) and scientific rows out of the plan makes the
    compatibility decision safe to inspect, serialize, and test independently.
    """
    releases = validated_lock.get("_validated_releases")
    if not isinstance(releases, dict) or not releases:
        raise ContractError("execution planning requires a validated slice lock")
    if not all(isinstance(release, ValidatedRelease) for release in releases.values()):
        raise ContractError("validated slice lock contains an invalid release resolution")

    identities = tuple(
        ReleaseIdentity(
            input_name=name,
            artifact_type=release.manifest["artifact_type"],
            release_id=release.manifest["release_id"],
            manifest_sha256=release.manifest_hash,
        )
        for name, release in sorted(releases.items())
    )
    roles = tuple(
        DirectInputRole(
            input_name=name,
            role=entry["role"],
            schema_identity=_freeze(entry["schema_identity"]),
            sha256=entry["sha256"],
        )
        for name, release in sorted(releases.items())
        for entry in release.manifest["files"]
    )

    kernel_authorized = bool(validated_lock["scientific_execution_authorized"])
    steps = [
        MaterializationStep("adapt_census", tuple(r.role for r in roles if r.input_name == "census")),
        MaterializationStep("adapt_income", tuple(r.role for r in roles if r.input_name == "income")),
        MaterializationStep("adapter_qa"),
    ]
    if kernel_authorized:
        steps.extend((MaterializationStep("scientific_kernel"), MaterializationStep("aggregate"), MaterializationStep("package")))

    return ExecutionPlan(
        slice_id=validated_lock["slice_id"],
        mode=validated_lock["mode"],
        releases=identities,
        selected_period=validated_lock["selected_period"],
        id_namespace=validated_lock["census"]["sample_id_namespace"],
        geography_vintage=validated_lock["census"]["geography_vintage"],
        monetary_reference=validated_lock["income"]["monetary_reference"],
        direct_input_roles=roles,
        approved_scientific_policies=_freeze(dict(validated_lock["approved_execution_policies"])),
        requested_outputs=_freeze(dict(validated_lock.get("outputs", {}))),
        materialization_steps=tuple(steps),
        kernel_authorized=kernel_authorized,
    )
