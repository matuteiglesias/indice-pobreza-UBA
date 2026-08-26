"""Population estimation over already-measured poverty contributions.

This layer knows weights and grouping domains, but it does not know poverty
thresholds, model inference, source geography, or geometry. A geography ID is a
grouping key only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from poverty_pipeline.science import PovertyMeasurement


class EstimationError(ValueError):
    pass


@dataclass(frozen=True)
class HouseholdDomain:
    household_id: str
    geography_level: str
    geography_id: str


@dataclass(frozen=True)
class HouseholdWeight:
    household_id: str
    analysis_weight: float


@dataclass(frozen=True)
class EstimationDesign:
    design_id: str
    weight_semantics: str
    weights: tuple[HouseholdWeight, ...]
    supports_population_totals: bool = False


@dataclass(frozen=True)
class EstimationContext:
    release_id: str
    estimation_period: str
    frame_vintage: str
    national_geography_id: str = "ARG"


@dataclass(frozen=True)
class PovertyEstimate:
    release_id: str
    estimation_period: str
    frame_vintage: str
    universe: str
    geography_level: str
    geography_id: str
    concept: str
    estimand: str
    estimate: float
    unit: str
    weighted_numerator: float
    weighted_denominator: float
    coverage: float
    design_id: str
    weight_semantics: str
    uncertainty_status: str


@dataclass(frozen=True)
class EstimationQA:
    household_rows: int
    person_rows: int
    domain_count: int
    min_analysis_weight: float
    max_analysis_weight: float
    national_reconciliation: str
    uncertainty_status: str


@dataclass(frozen=True)
class PovertyEstimation:
    estimates: tuple[PovertyEstimate, ...]
    qa: EstimationQA


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EstimationError(f"{label} must be a nonempty string")
    return value


def _positive(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EstimationError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise EstimationError(f"{label} must be finite and positive")
    return value


def _unique(rows: Iterable[object], key, label: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for row in rows:
        value = key(row)
        _text(value, f"{label} key")
        if value in result:
            raise EstimationError(f"duplicate {label} key: {value!r}")
        result[value] = row
    if not result:
        raise EstimationError(f"{label} rows must be nonempty")
    return result


def _contribution(row: object, concept: str, alpha: int, *, person: bool) -> float:
    prefix = "inherited_" if person else ""
    value = getattr(row, f"{prefix}{concept}_fgt{alpha}")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise EstimationError("FGT contribution must be finite numeric")
    value = float(value)
    if value < 0 or value > 1:
        raise EstimationError("FGT contribution must be within [0,1]")
    return value


def estimate_poverty(
    measurement: PovertyMeasurement,
    domains: Iterable[HouseholdDomain],
    design: EstimationDesign,
    context: EstimationContext,
) -> PovertyEstimation:
    """Estimate weighted FGT0/1/2 for one declared geography/domain level."""
    if not isinstance(measurement, PovertyMeasurement):
        raise EstimationError("an explicit PovertyMeasurement is required")
    for label, value in (("design ID", design.design_id), ("weight semantics", design.weight_semantics),
                         ("release ID", context.release_id), ("estimation period", context.estimation_period),
                         ("frame vintage", context.frame_vintage),
                         ("national geography ID", context.national_geography_id)):
        _text(value, label)

    households = _unique(measurement.households, lambda x: x.household_id, "measured household")
    persons = _unique(measurement.persons, lambda x: x.person_id, "measured person")
    domain_by_household = _unique(domains, lambda x: x.household_id, "household domain")
    weight_by_household = _unique(design.weights, lambda x: x.household_id, "household weight")
    household_ids = set(households)
    if set(domain_by_household) != household_ids or set(weight_by_household) != household_ids:
        raise EstimationError("domains and weights must exactly cover measured households")

    levels = {row.geography_level for row in domain_by_household.values()}
    if len(levels) != 1:
        raise EstimationError("one estimation run must declare exactly one geography level")
    geography_level = levels.pop()
    _text(geography_level, "geography level")
    for row in domain_by_household.values():
        _text(row.geography_id, "geography ID")
    weights = {key: _positive(row.analysis_weight, "analysis weight")
               for key, row in weight_by_household.items()}

    for person in persons.values():
        if person.household_id not in households:
            raise EstimationError(f"person references unknown measured household: {person.household_id!r}")

    cells: dict[tuple[str, str, str, str, int], list[float]] = {}

    def add(universe: str, household_id: str, row: object, *, person: bool) -> None:
        domain = domain_by_household[household_id]
        weight = weights[household_id]
        for concept in ("indigence", "poverty"):
            for alpha in (0, 1, 2):
                key = (universe, geography_level, domain.geography_id, concept, alpha)
                cell = cells.setdefault(key, [0.0, 0.0])
                cell[0] += weight * _contribution(row, concept, alpha, person=person)
                cell[1] += weight

    for household_id, row in households.items():
        add("households", household_id, row, person=False)
    for row in persons.values():
        add("persons", row.household_id, row, person=True)

    estimates: list[PovertyEstimate] = []
    for (universe, level, geography_id, concept, alpha), (numerator, denominator) in sorted(cells.items()):
        estimates.append(_row(context, design, universe, level, geography_id, concept, alpha,
                              numerator, denominator))

    for universe in ("households", "persons"):
        for concept in ("indigence", "poverty"):
            for alpha in (0, 1, 2):
                children = [row for row in estimates
                            if row.universe == universe and row.concept == concept
                            and row.estimand == f"fgt{alpha}" and row.geography_level == geography_level]
                if not children:
                    raise EstimationError("national reconciliation has no domain children")
                estimates.append(_row(
                    context, design, universe, "national", context.national_geography_id, concept, alpha,
                    sum(row.weighted_numerator for row in children),
                    sum(row.weighted_denominator for row in children),
                ))

    _validate_estimates(estimates)
    domain_count = len({row.geography_id for row in domain_by_household.values()})
    qa = EstimationQA(
        household_rows=len(households),
        person_rows=len(persons),
        domain_count=domain_count,
        min_analysis_weight=min(weights.values()),
        max_analysis_weight=max(weights.values()),
        national_reconciliation="passed",
        uncertainty_status="not_supplied",
    )
    return PovertyEstimation(tuple(estimates), qa)


def _row(context: EstimationContext, design: EstimationDesign, universe: str, level: str,
         geography_id: str, concept: str, alpha: int, numerator: float,
         denominator: float) -> PovertyEstimate:
    if denominator <= 0 or not math.isfinite(numerator) or not math.isfinite(denominator):
        raise EstimationError("weighted cells require finite positive denominator")
    estimate = numerator / denominator
    if estimate < 0 or estimate > 1:
        raise EstimationError("FGT estimate must be within [0,1]")
    return PovertyEstimate(
        release_id=context.release_id,
        estimation_period=context.estimation_period,
        frame_vintage=context.frame_vintage,
        universe=universe,
        geography_level=level,
        geography_id=geography_id,
        concept=concept,
        estimand=f"fgt{alpha}",
        estimate=estimate,
        unit="proportion",
        weighted_numerator=numerator,
        weighted_denominator=denominator,
        coverage=1.0,
        design_id=design.design_id,
        weight_semantics=design.weight_semantics,
        uncertainty_status="not_supplied",
    )


def _validate_estimates(rows: Iterable[PovertyEstimate]) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = (row.release_id, row.estimation_period, row.universe, row.geography_level,
               row.geography_id, row.concept, row.estimand)
        if key in seen:
            raise EstimationError(f"duplicate poverty estimate key: {key!r}")
        seen.add(key)
        if row.coverage != 1.0:
            raise EstimationError("first v2 estimator requires complete measured coverage")
        if row.uncertainty_status != "not_supplied":
            raise EstimationError("point estimator must not invent uncertainty")
