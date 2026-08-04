"""Standard-library validation for immutable research artifact releases."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_SCHEMA = "research-artifact-manifest/v1"
ALLOWED_TRANSFORMS = {"linear_ars", "log10_ars", "log10_ars_plus_1"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """An artifact or slice lock violates its declared contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON document {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"document must be an object: {path}")
    return value


def _require(obj: dict[str, Any], keys: set[str], context: str) -> None:
    missing = sorted(keys - obj.keys())
    if missing:
        raise ContractError(f"{context} missing required fields: {', '.join(missing)}")


def _safe_relative(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


@dataclass(frozen=True)
class ValidatedRelease:
    root: Path
    manifest: dict[str, Any]
    manifest_hash: str

    def role_path(self, role: str) -> Path:
        matches = [entry for entry in self.manifest["files"] if entry["role"] == role]
        if len(matches) != 1:
            raise ContractError(f"release must declare exactly one file with role {role!r}")
        return self.root / matches[0]["path"]


def validate_release(
    root: str | Path,
    *,
    expected_artifact_type: str,
    expected_identity: dict[str, Any] | None = None,
    allowed_statuses: set[str] = frozenset({"fixture"}),
) -> ValidatedRelease:
    """Validate the complete shared envelope before an adapter reads a table."""
    root = Path(root)
    manifest_path = root / "manifest.json"
    manifest = load_json(manifest_path)
    _require(manifest, {"schema_version", "artifact_type", "release_id", "status", "immutable",
             "producer", "period", "compatibility", "files", "reports", "limitations",
             "unresolved_blockers", "upstream_manifests"}, "manifest")
    if manifest["schema_version"] != MANIFEST_SCHEMA:
        raise ContractError("unsupported manifest schema version")
    if manifest["artifact_type"] != expected_artifact_type:
        raise ContractError("artifact type substitution is forbidden")
    if manifest["status"] not in allowed_statuses or manifest["immutable"] is not True:
        raise ContractError("release status/mode is not allowed or release is mutable")
    if not isinstance(manifest["release_id"], str) or not manifest["release_id"] or "latest" in manifest["release_id"].lower():
        raise ContractError("release_id must be immutable and may not use latest")
    producer = manifest["producer"]
    _require(producer, {"repository", "commit"}, "producer")
    if not re.fullmatch(r"[0-9a-f]{40}", str(producer["commit"])):
        raise ContractError("producer commit must be a full Git SHA")
    if any(token in str(producer["repository"]) for token in ("/raw/", "raw.githubusercontent.com", "/tree/")):
        raise ContractError("mutable or branch repository URLs are forbidden")
    if not isinstance(manifest["period"], str) or not manifest["period"]:
        raise ContractError("period/vintage is required")
    if not isinstance(manifest["limitations"], list) or not manifest["limitations"]:
        raise ContractError("limitations must be explicitly recorded")
    if not isinstance(manifest["unresolved_blockers"], list):
        raise ContractError("unresolved_blockers must be a list")
    if not isinstance(manifest["upstream_manifests"], list):
        raise ContractError("upstream manifest identities must be explicitly declared as a list")
    for upstream in manifest["upstream_manifests"]:
        _require(upstream, {"artifact_type", "release_id", "manifest_sha256"}, "upstream identity")
        if not HEX64.fullmatch(str(upstream["manifest_sha256"])):
            raise ContractError("upstream manifest identity has an invalid checksum")
    entries = list(manifest["files"]) + list(manifest["reports"])
    if not entries:
        raise ContractError("release contains no declared files or reports")
    paths: set[str] = set()
    for entry in entries:
        _require(entry, {"path", "role", "size", "sha256", "schema_identity"}, "envelope entry")
        relative = entry["path"]
        if not isinstance(relative, str) or not _safe_relative(relative) or relative in paths:
            raise ContractError(f"unsafe or duplicate release path: {relative!r}")
        paths.add(relative)
        if not HEX64.fullmatch(str(entry["sha256"])):
            raise ContractError(f"invalid checksum for {relative}")
        target = root / relative
        if not target.is_file():
            raise ContractError(f"declared release file missing: {relative}")
        if target.stat().st_size != entry["size"] or sha256_file(target) != entry["sha256"]:
            raise ContractError(f"size or checksum mismatch: {relative}")
    if expected_identity:
        for key, expected in expected_identity.items():
            actual = manifest["compatibility"].get(key)
            if actual != expected:
                raise ContractError(f"compatibility mismatch for {key}: {actual!r} != {expected!r}")
    return ValidatedRelease(root, manifest, sha256_file(manifest_path))


def validate_lock(path: str | Path) -> dict[str, Any]:
    """Validate a content-locked ``contracts_only`` slice and both releases."""
    path = Path(path)
    lock = load_json(path)  # JSON is intentionally used as the strict YAML subset.
    _require(lock, {"schema_version", "slice_id", "mode", "selected_period", "geography_level",
             "census", "income", "adult_equivalence", "regional_baskets", "geography",
             "approved_execution_policies", "versions", "unresolved_methodology",
             "scientific_execution_authorized"}, "slice lock")
    if lock["schema_version"] != "poverty-slice-lock/v1" or lock["mode"] != "contracts_only":
        raise ContractError("only poverty-slice-lock/v1 contracts_only locks are supported")
    if lock["scientific_execution_authorized"] is not False:
        raise ContractError("contracts_only cannot authorize scientific execution")
    if any("PENDING_" in str(value) for value in _walk(lock)):
        raise ContractError("execution lock contains a planning placeholder")
    if lock["adult_equivalence"].get("status") != "unresolved" or lock["regional_baskets"].get("status") != "unresolved":
        raise ContractError("method inputs must remain unresolved in contracts_only mode")
    policies = lock["approved_execution_policies"]
    if policies != {"join": "strict", "income_output_transform": "linear_ars", "allow_kernel": False}:
        raise ContractError("unapproved execution policy")
    base = path.parent
    releases: dict[str, ValidatedRelease] = {}
    for name, artifact_type in (("census", "research.census-sample/v1"), ("income", "research.person-income-predictions/v1")):
        pin = lock[name]
        _require(pin, {"release_id", "manifest_sha256", "path", "sample_id_namespace"}, f"{name} pin")
        release = validate_release((base / pin["path"]).resolve(), expected_artifact_type=artifact_type)
        if release.manifest["release_id"] != pin["release_id"] or release.manifest_hash != pin["manifest_sha256"]:
            raise ContractError(f"{name} release identity or manifest hash mismatch")
        releases[name] = release
    census_c = releases["census"].manifest["compatibility"]
    income_c = releases["income"].manifest["compatibility"]
    namespace = lock["census"]["sample_id_namespace"]
    if namespace != lock["income"]["sample_id_namespace"] or namespace != census_c.get("sample_id_namespace") or namespace != income_c.get("sample_id_namespace"):
        raise ContractError("sample-ID namespaces must match exactly")
    if any(release.manifest["period"] != lock["selected_period"] for release in releases.values()):
        raise ContractError("release period does not exactly match selected period")
    if census_c.get("person_schema") != "census-person/v1" or census_c.get("household_schema") != "census-household/v1":
        raise ContractError("Census file schema identities are incompatible")
    if income_c.get("entity") != "person" or income_c.get("prediction_schema") != "person-income-predictions/v1":
        raise ContractError("income entity or schema identity is incompatible")
    if income_c.get("prediction_transform") not in ALLOWED_TRANSFORMS or not income_c.get("monetary_reference"):
        raise ContractError("prediction transform or monetary reference is invalid")
    if (lock["income"].get("prediction_transform") != income_c["prediction_transform"] or
            lock["income"].get("monetary_reference") != income_c["monetary_reference"]):
        raise ContractError("income transform or monetary reference differs from slice lock")
    if lock["census"].get("geography_vintage") != census_c.get("geography_vintage"):
        raise ContractError("Census geography vintage differs from slice lock")
    lock["_validated_releases"] = releases
    return lock


def _walk(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)
    else:
        yield value
