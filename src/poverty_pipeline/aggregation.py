"""Pure weighted aggregation of already-classified poverty tables.

This boundary deliberately knows nothing about thresholds or income.  Its only
inputs are classifications produced by the scientific kernel and the approved
sample weights carried by the household table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


class AggregationError(ValueError):
    """Classified inputs or an aggregate violate the publication contract."""


@dataclass(frozen=True)
class ClassifiedHousehold:
    household_id: str
    department_id: str
    poverty: bool
    indigence: bool
    sample_weight: float


@dataclass(frozen=True)
class ClassifiedPerson:
    person_id: str
    household_id: str


@dataclass(frozen=True)
class AggregateContext:
    release: str
    period: str
    geography_level: str = "department_2010"
    national_geography_id: str = "ARG"


@dataclass(frozen=True)
class TidyEstimate:
    """One row of the stable, serialization-independent aggregate contract."""

    release: str
    period: str
    universe: str
    geography_level: str
    geography_id: str
    observable: str
    statistic: str
    value: float
    unit: str
    numerator: float
    denominator: float
    coverage: float
    weight_policy: str


KEY_FIELDS = ("release", "period", "universe", "geography_level",
              "geography_id", "observable", "statistic")
WEIGHT_POLICY = "approved_household_sample_weight"


def _number(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AggregationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise AggregationError(f"{label} must be finite and {qualifier}")
    return result


def aggregate_classified_tables(
    persons: Iterable[ClassifiedPerson],
    households: Iterable[ClassifiedHousehold],
    context: AggregateContext,
    *,
    weight_policy: str = WEIGHT_POLICY,
) -> tuple[TidyEstimate, ...]:
    """Return department rows followed by their reconciled national rows.

    Persons inherit the approved household weight and classification.  Thus a
    household contributes its weight once to the household universe and once
    per resident to the person universe.  Missing classifications and orphaned
    people are errors rather than implicit exclusions.
    """
    if not isinstance(context, AggregateContext):
        raise AggregationError("an explicit AggregateContext is required")
    if context.geography_level != "department_2010":
        raise AggregationError("only department_2010 aggregation is supported")
    for label, value in (("release", context.release), ("period", context.period),
                         ("geography level", context.geography_level),
                         ("national geography ID", context.national_geography_id),
                         ("weight policy", weight_policy)):
        if not isinstance(value, str) or not value.strip():
            raise AggregationError(f"{label} must be nonempty")

    by_household: dict[str, ClassifiedHousehold] = {}
    for row in households:
        if row.household_id in by_household:
            raise AggregationError(f"duplicate household key: {row.household_id!r}")
        if not row.household_id or not row.department_id:
            raise AggregationError("household and department IDs must be nonempty")
        if not isinstance(row.poverty, bool) or not isinstance(row.indigence, bool):
            raise AggregationError("poverty classifications must be boolean")
        _number(row.sample_weight, "sample weight", positive=True)
        by_household[row.household_id] = row
    if not by_household:
        raise AggregationError("classified household table must be nonempty")

    person_rows = tuple(persons)
    seen_people: set[str] = set()
    for row in person_rows:
        if not row.person_id or row.person_id in seen_people:
            raise AggregationError(f"empty or duplicate person key: {row.person_id!r}")
        seen_people.add(row.person_id)
        if row.household_id not in by_household:
            raise AggregationError(f"person references unknown household: {row.household_id!r}")
    if not person_rows:
        raise AggregationError("classified person table must be nonempty")

    contributions: dict[tuple[str, str, str], list[float]] = {}
    def add(universe: str, household: ClassifiedHousehold) -> None:
        weight = float(household.sample_weight)
        for observable in ("poverty", "indigence"):
            key = (universe, household.department_id, observable)
            cell = contributions.setdefault(key, [0.0, 0.0])
            cell[0] += weight if getattr(household, observable) else 0.0
            cell[1] += weight

    for household in by_household.values():
        add("households", household)
    for person in person_rows:
        add("persons", by_household[person.household_id])

    rows: list[TidyEstimate] = []
    for (universe, department, observable), (numerator, denominator) in sorted(contributions.items()):
        rows.append(_estimate(context, universe, context.geography_level, department,
                              observable, numerator, denominator, weight_policy))
    for universe in ("households", "persons"):
        for observable in ("indigence", "poverty"):
            children = [r for r in rows if r.universe == universe and r.observable == observable]
            rows.append(_estimate(context, universe, "national", context.national_geography_id,
                                  observable, sum(r.numerator for r in children),
                                  sum(r.denominator for r in children), weight_policy))
    validate_tidy_estimates(rows)
    reconcile_national_to_departments(rows, national_geography_id=context.national_geography_id)
    return tuple(rows)


def _estimate(context: AggregateContext, universe: str, level: str, geography_id: str,
              observable: str, numerator: float, denominator: float,
              weight_policy: str) -> TidyEstimate:
    _number(numerator, "numerator")
    _number(denominator, "denominator", positive=True)
    if numerator > denominator:
        raise AggregationError("numerator must not exceed denominator")
    return TidyEstimate(context.release, context.period, universe, level, geography_id,
                        observable, "weighted_rate", numerator / denominator, "proportion",
                        numerator, denominator, 1.0, weight_policy)


def validate_tidy_estimates(rows: Iterable[TidyEstimate]) -> None:
    """Enforce unique keys and finite/nonnegative aggregate domains."""
    seen = set()
    for row in rows:
        key = tuple(getattr(row, field) for field in KEY_FIELDS)
        if key in seen:
            raise AggregationError(f"duplicate tidy aggregate key: {key!r}")
        seen.add(key)
        for field in ("value", "numerator", "denominator", "coverage"):
            _number(getattr(row, field), field, positive=(field == "denominator"))
        if row.numerator > row.denominator:
            raise AggregationError("numerator must not exceed denominator")
        if row.value > 1 or row.coverage > 1:
            raise AggregationError("proportions and coverage must not exceed one")
        if not math.isclose(row.value, row.numerator / row.denominator, rel_tol=1e-12, abs_tol=1e-15):
            raise AggregationError("value does not equal numerator / denominator")


def reconcile_national_to_departments(rows: Iterable[TidyEstimate], *,
                                      national_geography_id: str = "ARG") -> None:
    """Check each national numerator/denominator against department children."""
    materialized = tuple(rows)
    nationals = [r for r in materialized if r.geography_level == "national"]
    for national in nationals:
        children = [r for r in materialized
                    if r.release == national.release and r.period == national.period
                    and r.universe == national.universe and r.observable == national.observable
                    and r.statistic == national.statistic
                    and r.geography_level == "department_2010"]
        if national.geography_id != national_geography_id or not children:
            raise AggregationError("national row has no valid department reconciliation set")
        for field in ("numerator", "denominator"):
            if not math.isclose(getattr(national, field), sum(getattr(x, field) for x in children),
                                rel_tol=1e-12, abs_tol=1e-12):
                raise AggregationError(f"national {field} does not reconcile to departments")
