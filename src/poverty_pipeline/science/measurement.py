"""Pure household/person poverty measurement with FGT contributions.

This module accepts already-normalized in-memory scientific values. It does not
read files, validate release manifests, apply weights, perform geography work,
retransform model predictions, or write publication artifacts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, TypeVar

from .method import MethodContractError, PovertyMethod


class MeasurementError(ValueError):
    """The normalized scientific inputs cannot support poverty measurement."""


@dataclass(frozen=True)
class PersonMember:
    person_id: str
    household_id: str
    sex: str
    age: int


@dataclass(frozen=True)
class HouseholdWelfare:
    household_id: str
    amount: float


@dataclass(frozen=True)
class HouseholdPovertyLines:
    household_id: str
    cba_per_adult_equivalent: float
    cbt_per_adult_equivalent: float


@dataclass(frozen=True)
class HouseholdPovertyMeasure:
    household_id: str
    welfare: float
    person_count: int
    adult_equivalents: float
    household_cba: float
    household_cbt: float
    indigent: bool
    poor: bool
    indigence_fgt0: float
    indigence_fgt1: float
    indigence_fgt2: float
    poverty_fgt0: float
    poverty_fgt1: float
    poverty_fgt2: float
    indigence_monetary_shortfall: float
    poverty_monetary_shortfall: float


@dataclass(frozen=True)
class PersonPovertyMeasure:
    """Person contribution inherited from the person's household.

    FGT1/FGT2 here are explicitly inherited household normalized shortfalls.
    They are not produced by comparing individual welfare with an individual
    poverty line.
    """

    person_id: str
    household_id: str
    indigent: bool
    poor: bool
    inherited_indigence_fgt0: float
    inherited_indigence_fgt1: float
    inherited_indigence_fgt2: float
    inherited_poverty_fgt0: float
    inherited_poverty_fgt1: float
    inherited_poverty_fgt2: float


@dataclass(frozen=True)
class PovertyMeasurement:
    households: tuple[HouseholdPovertyMeasure, ...]
    persons: tuple[PersonPovertyMeasure, ...]


T = TypeVar("T")


def _unique(records: Iterable[T], key, label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for record in records:
        record_key = key(record)
        if not isinstance(record_key, str) or not record_key:
            raise MeasurementError(f"{label} key must be a nonempty string")
        if record_key in result:
            raise MeasurementError(f"duplicate {label} key: {record_key!r}")
        result[record_key] = record
    return result


def _finite_nonnegative(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise MeasurementError(f"{label} must be finite and {qualifier}")
    return result


def _fgt_contribution(welfare: float, line: float, alpha: int, *, at_or_below: bool) -> float:
    if alpha not in (0, 1, 2):
        raise MeasurementError(f"unsupported FGT alpha: {alpha}")
    under = welfare <= line if at_or_below else welfare < line
    if not under:
        return 0.0
    if alpha == 0:
        return 1.0
    normalized_shortfall = max((line - welfare) / line, 0.0)
    return normalized_shortfall ** alpha


def measure_poverty(
    persons: Iterable[PersonMember],
    household_welfare: Iterable[HouseholdWelfare],
    household_lines: Iterable[HouseholdPovertyLines],
    method: PovertyMethod,
) -> PovertyMeasurement:
    """Measure household poverty and inherited person contributions.

    The function deliberately stops before population estimation. Sample weights,
    replicate weights, domains and uncertainty draws belong to later layers.
    """
    if not isinstance(method, PovertyMethod):
        raise MeasurementError("an explicit PovertyMethod is required")
    if method.welfare_entity != "household" or method.welfare_transform != "linear_currency":
        raise MeasurementError("measurement requires already-linear household welfare")
    if method.comparison != "at_or_below":
        raise MeasurementError("unsupported poverty-method comparison semantics")
    if method.person_inheritance != "inherits_household_status":
        raise MeasurementError("unsupported person inheritance semantics")
    if method.fgt_alphas != (0, 1, 2):
        raise MeasurementError("measurement kernel requires canonical FGT0/1/2 method semantics")

    person_by_id = _unique(persons, lambda row: row.person_id, "person")
    welfare_by_household = _unique(household_welfare, lambda row: row.household_id, "welfare household")
    lines_by_household = _unique(household_lines, lambda row: row.household_id, "line household")
    if not person_by_id or not welfare_by_household:
        raise MeasurementError("persons and household welfare must be nonempty")
    if set(welfare_by_household) != set(lines_by_household):
        raise MeasurementError("poverty-line coverage must exactly match household welfare")

    members_by_household: dict[str, list[PersonMember]] = {key: [] for key in welfare_by_household}
    for person in person_by_id.values():
        if not person.household_id:
            raise MeasurementError("person household_id must be nonempty")
        if person.household_id not in members_by_household:
            raise MeasurementError(f"person references unknown household: {person.household_id!r}")
        members_by_household[person.household_id].append(person)
    empty_households = sorted(key for key, members in members_by_household.items() if not members)
    if empty_households:
        raise MeasurementError(f"every measured household must contain at least one person: {empty_households!r}")

    household_results: list[HouseholdPovertyMeasure] = []
    for household_id in sorted(welfare_by_household):
        welfare = _finite_nonnegative(welfare_by_household[household_id].amount, "household welfare")
        lines = lines_by_household[household_id]
        cba_per_ae = _finite_nonnegative(
            lines.cba_per_adult_equivalent, "CBA per adult equivalent", positive=True
        )
        cbt_per_ae = _finite_nonnegative(
            lines.cbt_per_adult_equivalent, "CBT per adult equivalent", positive=True
        )
        if cba_per_ae > cbt_per_ae:
            raise MeasurementError("CBA per adult equivalent must not exceed CBT")

        adult_equivalents = 0.0
        for person in members_by_household[household_id]:
            try:
                adult_equivalents += method.adult_equivalence(sex=person.sex, age=person.age)
            except MethodContractError as exc:
                raise MeasurementError(
                    f"invalid demographic method coverage for person {person.person_id!r}: {exc}"
                ) from exc
        adult_equivalents = _finite_nonnegative(
            adult_equivalents, "household adult equivalents", positive=True
        )
        household_cba = cba_per_ae * adult_equivalents
        household_cbt = cbt_per_ae * adult_equivalents
        indigent = welfare <= household_cba
        poor = welfare <= household_cbt
        if indigent and not poor:
            raise MeasurementError("indigence must imply poverty when CBA <= CBT")

        household_results.append(HouseholdPovertyMeasure(
            household_id=household_id,
            welfare=welfare,
            person_count=len(members_by_household[household_id]),
            adult_equivalents=adult_equivalents,
            household_cba=household_cba,
            household_cbt=household_cbt,
            indigent=indigent,
            poor=poor,
            indigence_fgt0=_fgt_contribution(welfare, household_cba, 0, at_or_below=True),
            indigence_fgt1=_fgt_contribution(welfare, household_cba, 1, at_or_below=True),
            indigence_fgt2=_fgt_contribution(welfare, household_cba, 2, at_or_below=True),
            poverty_fgt0=_fgt_contribution(welfare, household_cbt, 0, at_or_below=True),
            poverty_fgt1=_fgt_contribution(welfare, household_cbt, 1, at_or_below=True),
            poverty_fgt2=_fgt_contribution(welfare, household_cbt, 2, at_or_below=True),
            indigence_monetary_shortfall=max(household_cba - welfare, 0.0),
            poverty_monetary_shortfall=max(household_cbt - welfare, 0.0),
        ))

    household_result_by_id = {row.household_id: row for row in household_results}
    person_results: list[PersonPovertyMeasure] = []
    for person_id in sorted(person_by_id):
        person = person_by_id[person_id]
        household = household_result_by_id[person.household_id]
        person_results.append(PersonPovertyMeasure(
            person_id=person.person_id,
            household_id=person.household_id,
            indigent=household.indigent,
            poor=household.poor,
            inherited_indigence_fgt0=household.indigence_fgt0,
            inherited_indigence_fgt1=household.indigence_fgt1,
            inherited_indigence_fgt2=household.indigence_fgt2,
            inherited_poverty_fgt0=household.poverty_fgt0,
            inherited_poverty_fgt1=household.poverty_fgt1,
            inherited_poverty_fgt2=household.poverty_fgt2,
        ))

    return PovertyMeasurement(tuple(household_results), tuple(person_results))
