"""Predictive household poverty measurement from a marginal welfare distribution.

This module is intentionally parallel to ``measurement.py``.  It does not alter
point-welfare semantics.  It integrates household FGT contributions over a
shared additive empirical residual distribution supplied by an upstream welfare
producer.

The supported first representation is::

    Y_h = max(0, location_h + R)

where ``R`` is a governed empirical household residual distribution.  Because
population FGT point estimands are averages of household contributions, only
marginal welfare distributions are required here.  This module does *not*
construct aggregate standard errors or confidence intervals.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Iterable, Sequence, TypeVar

from .measurement import HouseholdPovertyLines, PersonMember
from .method import MethodContractError, PovertyMethod


class PredictiveMeasurementError(ValueError):
    """Predictive welfare inputs cannot support poverty measurement."""


@dataclass(frozen=True)
class PredictiveHouseholdWelfare:
    household_id: str
    location: float
    estimation_status: str = "estimated"


@dataclass(frozen=True)
class EmpiricalResidualDistribution:
    """Shared additive empirical residual distribution.

    ``residuals`` are household-level calibration residuals in the same linear
    monetary reference as ``PredictiveHouseholdWelfare.location``.
    """

    residuals: tuple[float, ...]
    support_policy: str = "floor_at_zero"


@dataclass(frozen=True)
class PredictiveHouseholdPovertyMeasure:
    household_id: str
    point_welfare: float
    person_count: int
    adult_equivalents: float
    household_cba: float
    household_cbt: float
    indigence_probability: float
    expected_indigence_fgt1: float
    expected_indigence_fgt2: float
    poverty_probability: float
    expected_poverty_fgt1: float
    expected_poverty_fgt2: float

    @property
    def indigence_fgt0(self) -> float:
        return self.indigence_probability

    @property
    def poverty_fgt0(self) -> float:
        return self.poverty_probability

    @property
    def indigence_fgt1(self) -> float:
        return self.expected_indigence_fgt1

    @property
    def indigence_fgt2(self) -> float:
        return self.expected_indigence_fgt2

    @property
    def poverty_fgt1(self) -> float:
        return self.expected_poverty_fgt1

    @property
    def poverty_fgt2(self) -> float:
        return self.expected_poverty_fgt2


@dataclass(frozen=True)
class PredictivePersonPovertyMeasure:
    person_id: str
    household_id: str
    inherited_indigence_fgt0: float
    inherited_indigence_fgt1: float
    inherited_indigence_fgt2: float
    inherited_poverty_fgt0: float
    inherited_poverty_fgt1: float
    inherited_poverty_fgt2: float


@dataclass(frozen=True)
class PredictivePovertyMeasurement:
    households: tuple[PredictiveHouseholdPovertyMeasure, ...]
    persons: tuple[PredictivePersonPovertyMeasure, ...]
    measurement_mode: str = "predictive_marginal_integrated"
    uncertainty_status: str = "not_supplied"


T = TypeVar("T")


def _unique(records: Iterable[T], key, label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for record in records:
        record_key = key(record)
        if not isinstance(record_key, str) or not record_key:
            raise PredictiveMeasurementError(f"{label} key must be a nonempty string")
        if record_key in result:
            raise PredictiveMeasurementError(f"duplicate {label} key: {record_key!r}")
        result[record_key] = record
    return result


def _finite_nonnegative(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PredictiveMeasurementError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out) or out < 0 or (positive and out == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise PredictiveMeasurementError(f"{label} must be finite and {qualifier}")
    return out


class _ResidualIndex:
    """Sorted ECDF with prefix moments for exact empirical FGT integration."""

    def __init__(self, distribution: EmpiricalResidualDistribution):
        if distribution.support_policy != "floor_at_zero":
            raise PredictiveMeasurementError(
                "first predictive welfare contract requires support_policy='floor_at_zero'"
            )
        if not distribution.residuals:
            raise PredictiveMeasurementError("residual distribution must be nonempty")
        values = sorted(float(x) for x in distribution.residuals)
        if any(not math.isfinite(x) for x in values):
            raise PredictiveMeasurementError("residual distribution must be finite")
        self.r = values
        self.n = len(values)
        self.s1 = [0.0]
        self.s2 = [0.0]
        for value in values:
            self.s1.append(self.s1[-1] + value)
            self.s2.append(self.s2[-1] + value * value)

    def expected_fgt(self, location: float, line: float) -> tuple[float, float, float]:
        """Return exact empirical E[FGT0], E[FGT1], E[FGT2].

        For positive line ``L`` and ``Y=max(0, mu+R)``:
        - R <= -mu contributes welfare zero, hence FGT1=FGT2=1;
        - -mu < R <= L-mu contributes powers of ``(L-mu-R)/L``;
        - larger residuals contribute zero.
        Prefix moments make evaluation O(log n) per household.
        """
        mu = _finite_nonnegative(location, "predictive welfare location")
        L = _finite_nonnegative(line, "poverty line", positive=True)
        zero_cut = -mu
        line_cut = L - mu
        k0 = bisect.bisect_right(self.r, zero_cut)
        k1 = bisect.bisect_right(self.r, line_cut)
        # If L > 0, line_cut always exceeds zero_cut, but retain a defensive guard.
        if k1 < k0:
            k1 = k0
        n_mid = k1 - k0
        sum_r = self.s1[k1] - self.s1[k0]
        sum_r2 = self.s2[k1] - self.s2[k0]
        t = line_cut

        fgt0 = k1 / self.n
        gap1_sum = k0 + (n_mid * t - sum_r) / L
        gap2_sum = k0 + (n_mid * t * t - 2.0 * t * sum_r + sum_r2) / (L * L)
        # Numerical round-off only; mathematically all three are in [0,1].
        return tuple(min(1.0, max(0.0, x)) for x in (fgt0, gap1_sum / self.n, gap2_sum / self.n))


def measure_predictive_poverty(
    persons: Iterable[PersonMember],
    household_welfare: Iterable[PredictiveHouseholdWelfare],
    household_lines: Iterable[HouseholdPovertyLines],
    method: PovertyMethod,
    residual_distribution: EmpiricalResidualDistribution,
) -> PredictivePovertyMeasurement:
    """Integrate household FGT0/1/2 over marginal predictive welfare.

    This function deliberately stops before population estimation.  The returned
    household/person FGT fields are already expected contributions and may be
    aggregated by the generic estimation layer.  ``uncertainty_status`` remains
    ``not_supplied`` because marginal integration is not an aggregate sampling or
    model-uncertainty interval.
    """
    if not isinstance(method, PovertyMethod):
        raise PredictiveMeasurementError("an explicit PovertyMethod is required")
    if method.welfare_entity != "household" or method.welfare_transform != "linear_currency":
        raise PredictiveMeasurementError("predictive measurement requires linear household welfare")
    if method.comparison != "at_or_below":
        raise PredictiveMeasurementError("unsupported poverty-method comparison semantics")
    if method.person_inheritance != "inherits_household_status":
        raise PredictiveMeasurementError("unsupported person inheritance semantics")
    if method.fgt_alphas != (0, 1, 2):
        raise PredictiveMeasurementError("predictive measurement requires canonical FGT0/1/2 semantics")

    person_by_id = _unique(persons, lambda row: row.person_id, "person")
    welfare_by_household = _unique(household_welfare, lambda row: row.household_id, "welfare household")
    lines_by_household = _unique(household_lines, lambda row: row.household_id, "line household")
    if not person_by_id or not welfare_by_household:
        raise PredictiveMeasurementError("persons and household welfare must be nonempty")
    if set(welfare_by_household) != set(lines_by_household):
        raise PredictiveMeasurementError("poverty-line coverage must exactly match predictive welfare")

    members: dict[str, list[PersonMember]] = {key: [] for key in welfare_by_household}
    for person in person_by_id.values():
        if person.household_id not in members:
            raise PredictiveMeasurementError(f"person references unknown household: {person.household_id!r}")
        members[person.household_id].append(person)
    empty = sorted(h for h, rows in members.items() if not rows)
    if empty:
        raise PredictiveMeasurementError(f"every measured household must contain a person: {empty!r}")

    residuals = _ResidualIndex(residual_distribution)
    household_results: list[PredictiveHouseholdPovertyMeasure] = []
    for household_id in sorted(welfare_by_household):
        welfare = welfare_by_household[household_id]
        if welfare.estimation_status != "estimated":
            raise PredictiveMeasurementError("predictive welfare requires estimation_status='estimated'")
        location = _finite_nonnegative(welfare.location, "predictive welfare location")
        line = lines_by_household[household_id]
        cba_per_ae = _finite_nonnegative(line.cba_per_adult_equivalent, "CBA per adult equivalent", positive=True)
        cbt_per_ae = _finite_nonnegative(line.cbt_per_adult_equivalent, "CBT per adult equivalent", positive=True)
        if cba_per_ae > cbt_per_ae:
            raise PredictiveMeasurementError("CBA per adult equivalent must not exceed CBT")

        adult_equivalents = 0.0
        for person in members[household_id]:
            try:
                adult_equivalents += method.adult_equivalence(sex=person.sex, age=person.age)
            except MethodContractError as exc:
                raise PredictiveMeasurementError(
                    f"invalid demographic method coverage for person {person.person_id!r}: {exc}"
                ) from exc
        adult_equivalents = _finite_nonnegative(adult_equivalents, "household adult equivalents", positive=True)
        household_cba = cba_per_ae * adult_equivalents
        household_cbt = cbt_per_ae * adult_equivalents
        i0, i1, i2 = residuals.expected_fgt(location, household_cba)
        p0, p1, p2 = residuals.expected_fgt(location, household_cbt)
        household_results.append(PredictiveHouseholdPovertyMeasure(
            household_id=household_id,
            point_welfare=location,
            person_count=len(members[household_id]),
            adult_equivalents=adult_equivalents,
            household_cba=household_cba,
            household_cbt=household_cbt,
            indigence_probability=i0,
            expected_indigence_fgt1=i1,
            expected_indigence_fgt2=i2,
            poverty_probability=p0,
            expected_poverty_fgt1=p1,
            expected_poverty_fgt2=p2,
        ))

    by_household = {row.household_id: row for row in household_results}
    person_results: list[PredictivePersonPovertyMeasure] = []
    for person_id in sorted(person_by_id):
        person = person_by_id[person_id]
        row = by_household[person.household_id]
        person_results.append(PredictivePersonPovertyMeasure(
            person_id=person.person_id,
            household_id=person.household_id,
            inherited_indigence_fgt0=row.indigence_fgt0,
            inherited_indigence_fgt1=row.indigence_fgt1,
            inherited_indigence_fgt2=row.indigence_fgt2,
            inherited_poverty_fgt0=row.poverty_fgt0,
            inherited_poverty_fgt1=row.poverty_fgt1,
            inherited_poverty_fgt2=row.poverty_fgt2,
        ))

    return PredictivePovertyMeasurement(tuple(household_results), tuple(person_results))
