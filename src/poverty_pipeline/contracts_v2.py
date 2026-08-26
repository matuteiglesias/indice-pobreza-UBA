"""Strict semantic handoffs for Poverty Estimation v2.

The classes here describe what Poverty consumes, not how sampler/model/line
producers construct their artifacts. No model, GIS, network or file I/O lives in
this module.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, TypeVar

from poverty_pipeline.science import HouseholdPovertyLines, HouseholdWelfare, PersonMember, PovertyMethod


class V2ContractError(ValueError):
    pass


@dataclass(frozen=True)
class PopulationFramePerson:
    person_id: str
    household_id: str
    sex: str
    age: int
    radio_2010_id: str
    department_2010_id: str
    province_2010_id: str


@dataclass(frozen=True)
class PopulationFrameHousehold:
    household_id: str
    department_2010_id: str
    province_2010_id: str
    frame_selection_probability: float
    analysis_weight: float


@dataclass(frozen=True)
class PopulationFrameRelease:
    release_id: str
    namespace: str
    frame_vintage: str
    sampling_design_id: str
    weight_semantics: str
    persons: tuple[PopulationFramePerson, ...]
    households: tuple[PopulationFrameHousehold, ...]


@dataclass(frozen=True)
class WelfareEstimate:
    household_id: str
    welfare_amount: float
    estimation_status: str = "estimated"


@dataclass(frozen=True)
class WelfareRelease:
    release_id: str
    frame_namespace: str
    welfare_period: str
    currency: str
    price_reference: str
    welfare_concept: str
    estimates: tuple[WelfareEstimate, ...]


@dataclass(frozen=True)
class PovertyLine:
    threshold_area_id: str
    cba_per_adult_equivalent: float
    cbt_per_adult_equivalent: float


@dataclass(frozen=True)
class PovertyLineRelease:
    release_id: str
    period: str
    currency: str
    price_reference: str
    method_release_id: str
    lines: tuple[PovertyLine, ...]


@dataclass(frozen=True)
class ThresholdAreaBinding:
    geography_level: str
    geography_id: str
    threshold_area_id: str


@dataclass(frozen=True)
class ThresholdAreaBindingRelease:
    release_id: str
    geography_level: str
    bindings: tuple[ThresholdAreaBinding, ...]


@dataclass(frozen=True)
class V2PreparedMeasurement:
    persons: tuple[PersonMember, ...]
    household_welfare: tuple[HouseholdWelfare, ...]
    household_lines: tuple[HouseholdPovertyLines, ...]


T = TypeVar("T")


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V2ContractError(f"{label} must be a nonempty string")
    return value


def _number(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2ContractError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise V2ContractError(f"{label} must be finite and {qualifier}")
    return value


def _unique(rows: Iterable[T], key, label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for row in rows:
        value = key(row)
        _text(value, f"{label} key")
        if value in result:
            raise V2ContractError(f"duplicate {label} key: {value!r}")
        result[value] = row
    if not result:
        raise V2ContractError(f"{label} rows must be nonempty")
    return result


def validate_population_frame(frame: PopulationFrameRelease) -> None:
    for label, value in (("release", frame.release_id), ("namespace", frame.namespace),
                         ("frame vintage", frame.frame_vintage),
                         ("sampling design", frame.sampling_design_id),
                         ("weight semantics", frame.weight_semantics)):
        _text(value, label)
    households = _unique(frame.households, lambda x: x.household_id, "frame household")
    people = _unique(frame.persons, lambda x: x.person_id, "frame person")
    for h in households.values():
        _text(h.department_2010_id, "department_2010_id")
        _text(h.province_2010_id, "province_2010_id")
        probability = _number(h.frame_selection_probability, "selection probability", positive=True)
        if probability > 1:
            raise V2ContractError("frame selection probability must not exceed one")
        _number(h.analysis_weight, "analysis weight", positive=True)
    represented: set[str] = set()
    for p in people.values():
        if p.household_id not in households:
            raise V2ContractError(f"person references unknown household: {p.household_id!r}")
        h = households[p.household_id]
        if (p.department_2010_id, p.province_2010_id) != (h.department_2010_id, h.province_2010_id):
            raise V2ContractError("person/household geography identity mismatch")
        for label, value in (("sex", p.sex), ("radio_2010_id", p.radio_2010_id),
                             ("department_2010_id", p.department_2010_id),
                             ("province_2010_id", p.province_2010_id)):
            _text(value, label)
        if isinstance(p.age, bool) or not isinstance(p.age, int) or p.age < 0:
            raise V2ContractError("age must be a nonnegative completed-year integer")
        represented.add(p.household_id)
    if represented != set(households):
        raise V2ContractError("every frame household must contain at least one person")


def validate_welfare_release(welfare: WelfareRelease, frame: PopulationFrameRelease) -> None:
    for label, value in (("release", welfare.release_id), ("frame namespace", welfare.frame_namespace),
                         ("welfare period", welfare.welfare_period), ("currency", welfare.currency),
                         ("price reference", welfare.price_reference),
                         ("welfare concept", welfare.welfare_concept)):
        _text(value, label)
    if welfare.frame_namespace != frame.namespace:
        raise V2ContractError("welfare release frame namespace mismatch")
    estimates = _unique(welfare.estimates, lambda x: x.household_id, "welfare household")
    if set(estimates) != {h.household_id for h in frame.households}:
        raise V2ContractError("welfare household coverage must exactly match the frame")
    for row in estimates.values():
        _number(row.welfare_amount, "welfare amount")
        if row.estimation_status != "estimated":
            raise V2ContractError("point-estimate contract requires estimation_status='estimated'")


def validate_line_release(lines: PovertyLineRelease, method: PovertyMethod) -> None:
    for label, value in (("release", lines.release_id), ("period", lines.period),
                         ("currency", lines.currency), ("price reference", lines.price_reference),
                         ("method release", lines.method_release_id)):
        _text(value, label)
    if lines.method_release_id != method.release_id:
        raise V2ContractError("poverty lines must pin the exact poverty-method release")
    by_area = _unique(lines.lines, lambda x: x.threshold_area_id, "poverty line area")
    for row in by_area.values():
        cba = _number(row.cba_per_adult_equivalent, "CBA per adult equivalent", positive=True)
        cbt = _number(row.cbt_per_adult_equivalent, "CBT per adult equivalent", positive=True)
        if cba > cbt:
            raise V2ContractError("CBA must not exceed CBT")


def prepare_measurement_inputs(frame: PopulationFrameRelease, welfare: WelfareRelease,
                               lines: PovertyLineRelease, binding: ThresholdAreaBindingRelease,
                               method: PovertyMethod, *, estimation_period: str) -> V2PreparedMeasurement:
    """Resolve P2 inputs using IDs only; no geometry or model logic is allowed."""
    validate_population_frame(frame)
    validate_welfare_release(welfare, frame)
    validate_line_release(lines, method)
    _text(estimation_period, "estimation period")
    if welfare.welfare_period != estimation_period or lines.period != estimation_period:
        raise V2ContractError("welfare, line and estimation periods must match")
    if welfare.currency != lines.currency or welfare.price_reference != lines.price_reference:
        raise V2ContractError("welfare and poverty lines must share monetary reference")
    if welfare.welfare_concept != method.welfare_concept:
        raise V2ContractError("welfare concept does not match poverty method")
    if binding.geography_level != "department_2010":
        raise V2ContractError("first threshold-area binding supports department_2010 only")

    bindings = _unique(binding.bindings, lambda x: x.geography_id, "threshold-area binding")
    needed = {h.department_2010_id for h in frame.households}
    if set(bindings) != needed:
        raise V2ContractError("threshold-area binding must exactly cover frame departments")
    line_by_area = {row.threshold_area_id: row for row in lines.lines}
    for row in bindings.values():
        if row.geography_level != binding.geography_level:
            raise V2ContractError("binding row geography level mismatch")
        if row.threshold_area_id not in line_by_area:
            raise V2ContractError(f"binding references unknown threshold area: {row.threshold_area_id!r}")

    welfare_by_household = {row.household_id: row for row in welfare.estimates}
    people = tuple(PersonMember(p.person_id, p.household_id, p.sex, p.age) for p in frame.persons)
    welfare_input = tuple(HouseholdWelfare(h.household_id, welfare_by_household[h.household_id].welfare_amount)
                          for h in sorted(frame.households, key=lambda x: x.household_id))
    line_input = []
    for h in sorted(frame.households, key=lambda x: x.household_id):
        area = bindings[h.department_2010_id].threshold_area_id
        line = line_by_area[area]
        line_input.append(HouseholdPovertyLines(h.household_id,
                                                line.cba_per_adult_equivalent,
                                                line.cbt_per_adult_equivalent))
    return V2PreparedMeasurement(people, welfare_input, tuple(line_input))
