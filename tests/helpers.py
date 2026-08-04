from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path


def copy_release(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    return target


def rows(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_rows(path: Path, fields, values):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(values)


def rehash(release: Path, filename: str):
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    target = release / filename
    for entry in manifest["files"] + manifest["reports"]:
        if entry["path"] == filename:
            entry["size"] = target.stat().st_size
            entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

