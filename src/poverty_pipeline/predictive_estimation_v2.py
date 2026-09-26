"""Population estimation over predictive expected poverty contributions.

The deterministic v2 estimator remains unchanged.  This parallel path consumes
``PredictivePovertyMeasurement`` whose FGT fields are already expectations over
marginal predictive household welfare, then applies the same declared domains
and analysis weights used by v2 estimation.

No aggregate uncertainty is manufactured: marginal predictive integration is a
point-estimand calculation, not a standard error or confidence interval.
"""
from __future__ import annotations

from collections.abc import Iterable

from poverty_pipeline.estimation_v2 import (
    EstimationContext,
    EstimationDesign,
    EstimationError,
    EstimationQA,
    HouseholdDomain,
    PovertyEstimate,
    PovertyEstimation,
    _row,
    _validate_estimates,
)
from poverty_pipeline.science.predictive_measurement import PredictivePovertyMeasurement


def _unique(records: Iterable[object], key, label: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for record in records:
        value = key(record)
        if not isinstance(value, str) or not value:
            raise EstimationError(f"{label} key must be a nonempty string")
        if value in result:
            raise EstimationError(f"duplicate {label} key: {value!r}")
        result[value] = record
    if not result:
        raise EstimationError(f"{label} rows must be nonempty")
    return result


def _positive(value: float, label: str) -> float:
    import math

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EstimationError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out) or out <= 0:
        raise EstimationError(f"{label} must be finite and positive")
    return out


def _contribution(row: object, concept: str, alpha: int, *, person: bool) -> float:
    import math

    prefix = "inherited_" if person else ""
    value = getattr(row, f"{prefix}{concept}_fgt{alpha}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EstimationError("predictive FGT contribution must be numeric")
    out = float(value)
    if not math.isfinite(out) or out < 0 or out > 1:
        raise EstimationError("predictive FGT contribution must be finite within [0,1]")
    return out


def estimate_predictive_poverty(
    measurement: PredictivePovertyMeasurement,
    domains: Iterable[HouseholdDomain],
    design: EstimationDesign,
    context: EstimationContext,
) -> PovertyEstimation:
    if not isinstance(measurement, PredictivePovertyMeasurement):
        raise EstimationError("an explicit PredictivePovertyMeasurement is required")
    if measurement.measurement_mode != "predictive_marginal_integrated":
        raise EstimationError("unsupported predictive measurement mode")
    if measurement.uncertainty_status != "not_supplied":
        raise EstimationError("first predictive estimator does not accept aggregate uncertainty claims")

    households = _unique(measurement.households, lambda x: x.household_id, "predictive household")
    persons = _unique(measurement.persons, lambda x: x.person_id, "predictive person")
    domain_by_household = _unique(domains, lambda x: x.household_id, "household domain")
    weight_by_household = _unique(design.weights, lambda x: x.household_id, "household weight")
    household_ids = set(households)
    if set(domain_by_household) != household_ids or set(weight_by_household) != household_ids:
        raise EstimationError("domains and weights must exactly cover predictive households")

    levels = {row.geography_level for row in domain_by_household.values()}
    if len(levels) != 1:
        raise EstimationError("one estimation run must declare exactly one geography level")
    geography_level = levels.pop()
    if not isinstance(geography_level, str) or not geography_level:
        raise EstimationError("geography level must be nonempty")
    weights = {key: _positive(row.analysis_weight, "analysis weight") for key, row in weight_by_household.items()}
    aggregate_level, aggregate_id = context.aggregate_identity()

    for person in persons.values():
        if person.household_id not in households:
            raise EstimationError(f"person references unknown predictive household: {person.household_id!r}")

    cells: dict[tuple[str, str, str, str, int], list[float]] = {}

    def add(universe: str, household_id: str, row: object, *, person: bool) -> None:
        domain = domain_by_household[household_id]
        if not isinstance(domain.geography_id, str) or not domain.geography_id:
            raise EstimationError("geography ID must be nonempty")
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
        estimates.append(_row(context, design, universe, level, geography_id, concept, alpha, numerator, denominator))

    for universe in ("households", "persons"):
        for concept in ("indigence", "poverty"):
            for alpha in (0, 1, 2):
                children = [
                    row for row in estimates
                    if row.universe == universe
                    and row.concept == concept
                    and row.estimand == f"fgt{alpha}"
                    and row.geography_level == geography_level
                ]
                if not children:
                    raise EstimationError("aggregate reconciliation has no domain children")
                estimates.append(_row(
                    context,
                    design,
                    universe,
                    aggregate_level,
                    aggregate_id,
                    concept,
                    alpha,
                    sum(row.weighted_numerator for row in children),
                    sum(row.weighted_denominator for row in children),
                ))

    _validate_estimates(estimates)
    qa = EstimationQA(
        household_rows=len(households),
        person_rows=len(persons),
        domain_count=len({row.geography_id for row in domain_by_household.values()}),
        min_analysis_weight=min(weights.values()),
        max_analysis_weight=max(weights.values()),
        national_reconciliation="passed",
        uncertainty_status="not_supplied",
    )
    return PovertyEstimation(tuple(estimates), qa)
