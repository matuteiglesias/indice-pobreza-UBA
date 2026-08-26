"""Strict in-memory contracts for Poverty Estimation v2 producer handoffs.

These contracts describe the semantic boundary Poverty expects from upstream
producers. They intentionally do not know how sampler/model/line repositories
construct their artifacts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from poverty_pipeline.science import (
    HouseholdPovertyLines,
    HouseholdWelfare,
    PersonMember,
    PovertyMethod,
)


class V2ContractError(ValueError):
    """A v2 handoff is incomplete or semantically incompatible."""


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
    methodology_id: str
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


def _nonempty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V2ContractError(f"{label} must be a nonempty string")
    return value


def _finite(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2ContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise V2ContractError(f"{label} must be finite and {qualifier}")
    return result


def _unique(rows: Iterable[object], key, label: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for row in rows:
        value = key(row)
        _nonempty(value, f"{label} key")
        if value in result:
            raise V2ContractError(f"duplicate {label} key: {value!r}")
        result[value] = row
    if not result:
        raise V2ContractError(f"{label} rows must be nonempty")
    return result


def validate_population_frame(frame: PopulationFrameRelease) -> None:
    for label, value in (
        ("frame release_id", frame.release_id),
        ("frame namespace", frame.namespace),
        ("frame vintage", frame.frame_vintage),
        ("sampling design", frame.sampling_design_id),
        ("weight semantics", frame.weight_semantics),
    ):
        _nonempty(value, label)
    people = _unique(frame.persons, lambda x: x.person_id, "frame person")
    households = _unique(frame.households, lambda x: x.household_id, "frame household")
    for household in households.values():
        assert isinstance(household, PopulationFrameHousehold)
        _nonempty(household.department_2010_id, "department_2010_id")
        _nonempty(household.province_2010_id, "province_2010_id")
        p = _finite(household.frame_selection_probability, "frame selection probability", positive=True)
        if p > 1:
            raise V2ContractError("frame selection probability must not exceed one")
        _finite(household.analysis_weight, "analysis weight", positive=True)
    seen_households: set[str] = set()
    for person in people.values():
        assert isinstance(person, PopulationFramePerson)
        if person.household_id not in households:
            raise V2ContractError(f"person references unknown household: {person.household_id!r}")
        household = households[person.household_id]
        assert isinstance(household, PopulationFrameHousehold)
        if (person.department_2010_id, person.province_2010_id) != (
            household.department_2010_id,
            household.province_2010_id,
        ):
            raise V2ContractError("person/household geography identity mismatch")
        for label, value in (
            ("radio_2010_id", person.radio_2010_id),
            ("department_2010_id", person.department_2010_id),
            ("province_2010_id", person.province_2010_id),
            ("sex", person.sex),
        ):
            _nonempty(value, label)
        if isinstance(person.age, bool) or not isinstance(person.age, int) or person.age < 0:
            raise V2ContractError("age must be a nonnegative completed-year integer")
        seen_households.add(person.household_id)
    if seen_households != set(households):
        raise V2ContractError("every frame household must contain at least one person")


def validate_welfare_release(welfare: WelfareRelease, frame: PopulationFrameRelease) -> None:
    for label, value in (
        ("welfare release_id", welfare.release_id),
        ("frame namespace", welfare.frame_namespace),
        ("welfare period", welfare.welfare_period),
        ("currency", welfare.currency),
        ("price reference", welfare.price_reference),
        ("welfare concept", welfare.welfare_concept),
    ):
        _nonempty(value, label)
    if welfare.frame_namespace != frame.namespace:
        raise V2ContractError("welfare release frame namespace mismatch")
    estimates = _unique(welfare.estimates, lambda x: x.household_id, "welfare household")
    expected = {row.household_id for row in frame.households}
    if set(estimates) != expected:
        raise V2ContractError("welfare household coverage must exactly match the frame")
    for estimate in estimates.values():
        assert isinstance(estimate, WelfareEstimate)
        _finite(estimate.welfare_amount, "welfare amount")
        if estimate.estimation_status != "estimated":
            raise V2ContractError("v2 point-estimate fixture requires estimation_status='estimated'")


def validate_line_release(lines: PovertyLineRelease, method: PovertyMethod) -> None:
    for label, value in (
        ("line release_id", lines.release_id),
        ("line period", lines.period),
        ("line currency", lines.currency),
        ("line price reference", lines.price_reference),
        ("line methodology", lines.methodology_id),
    ):
        _nonempty(value, label)
    if lines.methodology_id != method.methodology_id:
        raise V2ContractError("poverty-line methodology does not match the poverty method")
    unique = _unique(lines.lines, lambda x: x.threshold_area_id, "poverty line area")
    for line in unique.values():
        assert isinstance(line, PovertyLine)
        cba = _finite(line.cba_per_adult_equivalent, "CBA per adult equivalent", positive=True)
        cbt = _finite(line.cbt_per_adult_equivalent, "CBT per adult equivalent", positive=True)
        if cba > cbt:
            raise V2ContractError("CBA must not exceed CBT")


def prepare_measurement_inputs(
    frame: PopulationFrameRelease,
    welfare: WelfareRelease,
    lines: PovertyLineRelease,
    binding: ThresholdAreaBindingRelease,
    method: PovertyMethod,
    *,
    estimation_period: str,
) -> V2PreparedMeasurement:
    """Validate exact handoffs and resolve lines without geography computation."""
    validate_population_frame(frame)
    validate_welfare_release(welfare, frame)
    validate_line_release(lines, method)
    _nonempty(estimation_period, "estimation period")
    if welfare.welfare_period != estimation_period or lines.period != estimation_period:
        raise V2ContractError("welfare, poverty-line and estimation periods must match")
    if welfare.currency != lines.currency or welfare.price_reference != lines.price_reference:
        raise V2ContractError("welfare and poverty lines must share currency and price reference")
    if welfare.welfare_concept != method.welfare_concept:
        raise V2ContractError("welfare concept does not match the poverty method")
    if binding.geography_level != "department_2010":
        raise V2ContractError("first v2 binding supports department_2010 only")

    bindings = _unique(binding.bindings, lambda x: x.geography_id, "threshold-area binding")
    line_by_area = {row.threshold_area_id: row for row in lines.lines}
    household_by_id = {row.household_id: row for row in frame.households}
    welfare_by_id = {row.household_id: row for row in welfare.estimates}
    needed_departments = {row.department_2010_id for row in frame.households}
    if set(bindings) != needed_departments:
        raise V2ContractError("threshold-area binding must exactly cover frame departments")
    for row in bindings.values():
        assert isinstance(row, ThresholdAreaBinding)
        if row.geography_level != binding.geography_level:
            raise V2ContractError("binding row geography level mismatch")
        if row.threshold_area_id not in line_by_area:
            raise V2ContractError(f"binding references unknown threshold area: {row.threshold_area_id!r}")

    people = tuple(
        PersonMember(row.person_id, row.household_id, row.sex, row.age)
        for row in frame.persons
    )
    household_welfare = tuple(
        HouseholdWelfare(household_id, welfare_by_id[household_id].welfare_amount)
        for household_id in sorted(household_by_id)
    )
    household_lines = []
    for household_id in sorted(household_by_id):
        household = household_by_id[household_id]
        binding_row = bindings[household.department_2010_id]
        assert isinstance(binding_row, ThresholdAreaBinding)
        line = line_by_area[binding_row.threshold_area_id]
        household_lines.append(HouseholdPovertyLines(
            household_id,
            line.cba_per_adult_equivalent,
            line.cbt_per_adult_equivalent,
        ))
    return V2PreparedMeasurement(people, household_welfare, tuple(household_lines))
