"""Deterministic release packaging, separate from science and publication."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from poverty_pipeline.aggregation import TidyEstimate, validate_tidy_estimates


class PackagingError(ValueError):
    """A release cannot be represented as a deterministic immutable bundle."""


TABLE_FIELDS = tuple(TidyEstimate.__dataclass_fields__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def write_release_bundle(
    destination: str | Path,
    estimates: Iterable[TidyEstimate],
    *,
    input_manifests: Sequence[Mapping[str, str]],
    policies: Mapping[str, object],
    software: Mapping[str, str],
    qa: Mapping[str, object] | None = None,
    limitations: Sequence[str],
) -> Path:
    """Write the canonical files atomically and refuse to replace a release.

    No clock, environment metadata, network service, or geospatial conversion is
    consulted, so identical arguments produce byte-identical files.
    """
    target = Path(destination)
    rows = tuple(sorted(estimates, key=lambda row: tuple(str(v) for v in asdict(row).values())))
    if not rows:
        raise PackagingError("at least one estimate is required")
    validate_tidy_estimates(rows)
    if not limitations or any(not isinstance(item, str) or not item.strip() for item in limitations):
        raise PackagingError("limitations must contain nonempty text")
    if target.exists():
        raise PackagingError(f"release destination already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        table = staging / "estimates.csv"
        with table.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TABLE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(asdict(row) for row in rows)
        qa_document = {
            "schema_version": "poverty-output-qa/v1",
            "finite_nonnegative_domains": "passed",
            "national_department_reconciliation": "passed",
            "estimate_rows": len(rows),
            **dict(qa or {}),
        }
        _write(staging / "qa.json", _json_bytes(qa_document))
        _write(staging / "limitations.md",
               ("# Limitations\n\n" + "".join(f"- {item.strip()}\n" for item in limitations)).encode("utf-8"))

        release_ids = sorted({row.release for row in rows})
        periods = sorted({row.period for row in rows})
        if len(release_ids) != 1 or len(periods) != 1:
            raise PackagingError("a bundle must contain exactly one release and period")
        manifest = {
            "schema_version": "poverty-output-manifest/v1",
            "release": release_ids[0], "period": periods[0],
            "input_manifests": sorted((dict(x) for x in input_manifests),
                                      key=lambda x: json.dumps(x, sort_keys=True)),
            "policies": dict(policies), "software": dict(software),
            "files": ["estimates.csv", "qa.json", "limitations.md", "checksums.sha256"],
            "publication_artifacts": [],
        }
        _write(staging / "manifest.json", _json_bytes(manifest))
        covered = ("estimates.csv", "limitations.md", "manifest.json", "qa.json")
        checksum_text = "".join(f"{_sha256(staging / name)}  {name}\n" for name in covered)
        _write(staging / "checksums.sha256", checksum_text.encode("ascii"))
        os.replace(staging, target)
    except Exception:
        for child in staging.iterdir():
            child.unlink()
        staging.rmdir()
        raise
    return target


def verify_release_bundle(destination: str | Path) -> None:
    """Verify the deterministic checksum inventory of an existing bundle."""
    root = Path(destination)
    checksum_path = root / "checksums.sha256"
    try:
        lines = checksum_path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise PackagingError(f"cannot read checksums: {exc}") from exc
    for line in lines:
        digest, separator, name = line.partition("  ")
        if not separator or Path(name).name != name or _sha256(root / name) != digest:
            raise PackagingError(f"checksum verification failed: {name!r}")
