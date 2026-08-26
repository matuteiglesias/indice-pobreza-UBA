"""Versioned poverty-method contracts, independent of data/model execution."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MethodContractError(ValueError):
    """A poverty-method document is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class AdultEquivalenceBand:
    sex: str
    age_min: int
    age_max: int | None
    coefficient: float

    def contains(self, age: int) -> bool:
        return age >= self.age_min and (self.age_max is None or age <= self.age_max)


@dataclass(frozen=True)
class PovertyMethod:
    """The scientific semantics required by the pure poverty measurement kernel."""

    method_id: str
    version: str
    welfare_entity: str
    welfare_concept: str
    welfare_transform: str
    comparison: str
    person_inheritance: str
    canonical_sexes: tuple[str, ...]
    adult_equivalence_bands: tuple[AdultEquivalenceBand, ...]
    fgt_alphas: tuple[int, ...]

    @property
    def release_id(self) -> str:
        return f"{self.method_id}@{self.version}"

    def adult_equivalence(self, *, sex: str, age: int) -> float:
        if sex not in self.canonical_sexes:
            raise MethodContractError(f"unsupported canonical sex: {sex!r}")
        if isinstance(age, bool) or not isinstance(age, int) or age < 0:
            raise MethodContractError("age must be a nonnegative integer in completed years")
        matches = [band for band in self.adult_equivalence_bands
                   if band.sex == sex and band.contains(age)]
        if len(matches) != 1:
            raise MethodContractError(
                f"adult-equivalence coverage must be exactly one band for sex={sex!r}, age={age}"
            )
        return matches[0].coefficient


def load_poverty_method(path: str | Path) -> PovertyMethod:
    """Load and strictly validate a `poverty-method/v1` JSON document."""
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodContractError(f"cannot read poverty method {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise MethodContractError("poverty method must be a JSON object")
    return poverty_method_from_dict(document)


def poverty_method_from_dict(document: dict[str, Any]) -> PovertyMethod:
    _keys(document, {
        "schema_version", "method_id", "version", "authority", "sources", "welfare",
        "thresholds", "person_inheritance", "adult_equivalence", "estimands",
    }, "poverty method")
    if document["schema_version"] != "poverty-method/v1":
        raise MethodContractError("unsupported poverty-method schema version")
    method_id = _text(document["method_id"], "method_id")
    version = _text(document["version"], "version")

    welfare = _mapping(document["welfare"], "welfare")
    _keys(welfare, {"entity", "concept", "required_transform", "nonnegative_required"}, "welfare")
    if welfare["entity"] != "household":
        raise MethodContractError("poverty-method/v1 requires household welfare")
    if welfare["required_transform"] != "linear_currency":
        raise MethodContractError("poverty-method/v1 requires already-linear monetary welfare")
    if welfare["nonnegative_required"] is not True:
        raise MethodContractError("poverty-method/v1 requires nonnegative welfare")

    thresholds = _mapping(document["thresholds"], "thresholds")
    _keys(thresholds, {"indigence", "poverty", "comparison", "require_cba_lte_cbt"}, "thresholds")
    if thresholds["comparison"] != "at_or_below":
        raise MethodContractError("method v1 freezes poverty/indigence comparison as at_or_below")
    if thresholds["require_cba_lte_cbt"] is not True:
        raise MethodContractError("method must reject CBA above CBT")
    if thresholds["indigence"] != "cba_per_adult_equivalent_times_household_adult_equivalents":
        raise MethodContractError("unsupported indigence threshold construction")
    if thresholds["poverty"] != "cbt_per_adult_equivalent_times_household_adult_equivalents":
        raise MethodContractError("unsupported poverty threshold construction")

    inheritance = document["person_inheritance"]
    if inheritance != "inherits_household_status":
        raise MethodContractError("method v1 requires persons to inherit household status")

    adult = _mapping(document["adult_equivalence"], "adult_equivalence")
    _keys(adult, {"canonical_sexes", "age_unit", "minimum_age", "cells"}, "adult_equivalence")
    if adult["age_unit"] != "completed_years" or adult["minimum_age"] != 0:
        raise MethodContractError("adult-equivalence age domain must be completed years from zero")
    sexes_raw = adult["canonical_sexes"]
    if (not isinstance(sexes_raw, list) or not sexes_raw
            or any(not isinstance(value, str) or not value for value in sexes_raw)
            or len(set(sexes_raw)) != len(sexes_raw)):
        raise MethodContractError("canonical_sexes must be a nonempty unique string list")
    sexes = tuple(sexes_raw)

    cells = adult["cells"]
    if not isinstance(cells, list) or not cells:
        raise MethodContractError("adult-equivalence cells must be a nonempty list")
    bands: list[AdultEquivalenceBand] = []
    for index, raw in enumerate(cells):
        raw = _mapping(raw, f"adult-equivalence cell {index}")
        _keys(raw, {"sex", "age_min", "age_max", "coefficient"}, f"adult-equivalence cell {index}")
        sex = raw["sex"]
        if sex not in sexes:
            raise MethodContractError(f"adult-equivalence cell uses unknown sex: {sex!r}")
        age_min = raw["age_min"]
        age_max = raw["age_max"]
        if isinstance(age_min, bool) or not isinstance(age_min, int) or age_min < 0:
            raise MethodContractError("adult-equivalence age_min must be a nonnegative integer")
        if age_max is not None and (
            isinstance(age_max, bool) or not isinstance(age_max, int) or age_max < age_min
        ):
            raise MethodContractError("adult-equivalence age_max must be null or >= age_min")
        coefficient = raw["coefficient"]
        if (isinstance(coefficient, bool) or not isinstance(coefficient, (int, float))
                or not math.isfinite(float(coefficient)) or float(coefficient) <= 0):
            raise MethodContractError("adult-equivalence coefficient must be finite and positive")
        bands.append(AdultEquivalenceBand(sex, age_min, age_max, float(coefficient)))
    _validate_complete_bands(tuple(bands), sexes)

    estimands = _mapping(document["estimands"], "estimands")
    _keys(estimands, {"fgt_alphas", "normalized_shortfall", "monetary_shortfall", "note"}, "estimands")
    alphas = estimands["fgt_alphas"]
    if alphas != [0, 1, 2]:
        raise MethodContractError("poverty-method/v1 canonical FGT alphas must be [0, 1, 2]")
    if estimands["normalized_shortfall"] != "max((line_minus_welfare)/line,0)":
        raise MethodContractError("unsupported normalized-shortfall definition")
    if estimands["monetary_shortfall"] != "max(line_minus_welfare,0)":
        raise MethodContractError("unsupported monetary-shortfall definition")

    return PovertyMethod(
        method_id=method_id,
        version=version,
        welfare_entity=welfare["entity"],
        welfare_concept=_text(welfare["concept"], "welfare concept"),
        welfare_transform=welfare["required_transform"],
        comparison=thresholds["comparison"],
        person_inheritance=inheritance,
        canonical_sexes=sexes,
        adult_equivalence_bands=tuple(bands),
        fgt_alphas=tuple(alphas),
    )


def _validate_complete_bands(
    bands: tuple[AdultEquivalenceBand, ...], sexes: tuple[str, ...]
) -> None:
    for sex in sexes:
        ordered = sorted((band for band in bands if band.sex == sex), key=lambda x: x.age_min)
        if not ordered or ordered[0].age_min != 0:
            raise MethodContractError(f"adult-equivalence coverage for {sex!r} must start at age 0")
        for left, right in zip(ordered, ordered[1:]):
            if left.age_max is None:
                raise MethodContractError("open-ended adult-equivalence band must be final")
            if right.age_min != left.age_max + 1:
                raise MethodContractError(f"adult-equivalence bands for {sex!r} must be gap-free")
        if ordered[-1].age_max is not None:
            raise MethodContractError(f"adult-equivalence coverage for {sex!r} must be open-ended")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MethodContractError(f"{label} must be an object")
    return value


def _keys(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - value.keys()
    if missing:
        raise MethodContractError(f"{label} missing required fields: {sorted(missing)!r}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MethodContractError(f"{label} must be a nonempty string")
    return value
