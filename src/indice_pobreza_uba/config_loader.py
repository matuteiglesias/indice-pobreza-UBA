from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PipelineConfig:
    raw: dict[str, Any]
    config_path: Path
    root_dir: Path

    @property
    def project(self) -> dict[str, Any]:
        return self.raw["project"]

    @property
    def run(self) -> dict[str, Any]:
        return self.raw["run"]

    @property
    def paths(self) -> dict[str, Path]:
        resolved: dict[str, Path] = {}
        for key, value in self.raw["paths"].items():
            resolved[key] = self._resolve_path(value)
        return resolved

    @property
    def inputs(self) -> dict[str, Any]:
        return self.raw["inputs"]

    @property
    def contracts(self) -> dict[str, Any]:
        return self.raw["contracts"]

    @property
    def execution(self) -> dict[str, Any]:
        return self.raw["execution"]

    @property
    def quality(self) -> dict[str, Any]:
        return self.raw["quality"]

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.root_dir / path).resolve()

    def artifact_path(
        self,
        stage_name: str,
        output_name: str,
        **fmt: Any,
    ) -> Path:
        stage_contract = self.contracts[stage_name]
        output_contract = stage_contract["outputs"][output_name]
        filename_pattern = output_contract["filename_pattern"]
        filename = filename_pattern.format(**fmt)

        stage_dir_key = {
            "stage_01_predict": "stage_predict_dir",
            "stage_02_poverty": "stage_poverty_dir",
            "stage_03_stats": "stage_stats_dir",
            "stage_04_geo": "stage_geo_dir",
        }[stage_name]

        return self.paths[stage_dir_key] / filename


def load_config(config_path: str | Path) -> PipelineConfig:
    config_path = Path(config_path).resolve()
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    root_dir_value = raw["paths"]["root_dir"]
    root_dir = (config_path.parent.parent / Path(root_dir_value)).resolve()

    return PipelineConfig(
        raw=raw,
        config_path=config_path,
        root_dir=root_dir,
    )