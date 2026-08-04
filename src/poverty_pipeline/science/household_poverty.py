"""Deterministic household poverty kernel.

This module deliberately accepts already-normalized, in-memory records.  It does
not discover files, validate artifact manifests, access the network, aggregate
published statistics, or write output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TypeVar


class PovertyInputError(ValueError):
    """Canonical scientific inputs are incomplete or internally inconsistent."""


class ComparisonPolicy(str, Enum):
    """Lock-controlled treatment of income exactly equal to a threshold."""

    BELOW = "below"
    AT_OR_BELOW = "at_or_below"


class GapSignPolicy(str, Enum):
    """Lock-controlled subtraction order for poverty and indigence gaps."""

    INCOME_MINUS_THRESHOLD = "income_minus_threshold"
    THRESHOLD_MINUS_INCOME = "threshold_minus_income"


class WeightUsePolicy(str, Enum):
    """The kernel retains weights but never computes weighted estimands."""

    RETAIN_FOR_PUBLICATION = "retain_for_publication"


@dataclass(frozen=True)
class PovertyPolicies:
    poverty_comparison: ComparisonPolicy
    indigence_comparison: ComparisonPolicy
    gap_sign: GapSignPolicy
    income_adequacy_approved: bool
    weight_use: WeightUsePolicy
    allowed_universe: str


@dataclass(frozen=True)
class ScientificDependencyContract:
    """Approved semantics of the four direct scientific dependencies.

    Lineage values are identifiers only.  The kernel never opens the upstream
    EPH, model, raw basket/IPC, or Census sampling artifacts they identify.
    """

    sample_id_namespace: str
    period: str
    universe: str
    census_sampling_provenance: str
    census_projection_provenance: str
    income_release_lineage: str
    income_transform: str
    income_currency: str
    income_price_reference: str
    income_classification: str
    adult_equivalence_methodology_version: str
    adult_equivalence_provenance: str
    adult_equivalence_sexes: tuple[str, ...]
    adult_equivalence_age_min: int
    adult_equivalence_age_max: int
    basket_provenance: str
    basket_currency: str
    basket_price_reference: str
    basket_unit: str


@dataclass(frozen=True)
class NormalizedPerson:
    person_id: str
    household_id: str
    sex: str
    age: int


@dataclass(frozen=True)
class Household:
    household_id: str
    region: str
    period: str
    geography_key: str
    sample_weight: float


@dataclass(frozen=True)
class LinearIncome:
    person_id: str
    amount: float


@dataclass(frozen=True)
class AdultEquivalenceCell:
    """An inclusive age interval within a normalized sex domain."""

    sex: str
    age_min: int
    age_max: int
    coefficient: float


@dataclass(frozen=True)
class RegionalPeriodBasket:
    region: str
    period: str
    cba: float
    cbt: float


@dataclass(frozen=True)
class PersonThreshold:
    person_id: str
    household_id: str
    income: float
    adult_equivalence: float
    cba: float
    cbt: float


@dataclass(frozen=True)
class HouseholdThresholds:
    household_id: str
    region: str
    period: str
    geography_key: str
    sample_weight: float
    person_count: int
    income: float
    adult_equivalence: float
    cba: float
    cbt: float


@dataclass(frozen=True)
class HouseholdPoverty(HouseholdThresholds):
    poverty: bool
    indigence: bool
    poverty_gap: float
    indigence_gap: float


T = TypeVar("T")


def _unique(records: Iterable[T], key, label: str) -> dict[object, T]:
    result: dict[object, T] = {}
    for record in records:
        record_key = key(record)
        if record_key in result:
            raise PovertyInputError(f"duplicate {label} key: {record_key!r}")
        result[record_key] = record
    return result


def _finite_nonnegative(value: float, label: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise PovertyInputError(f"{label} must be finite and nonnegative")
    return value


def build_person_thresholds(
    persons: Iterable[NormalizedPerson],
    households: Iterable[Household],
    incomes: Iterable[LinearIncome],
    equivalence_cells: Iterable[AdultEquivalenceCell],
    baskets: Iterable[RegionalPeriodBasket],
    contract: ScientificDependencyContract,
    policies: PovertyPolicies,
) -> tuple[PersonThreshold, ...]:
    """Join canonical inputs strictly and construct person-level thresholds."""
    _validate_dependency_contract(contract, policies)
    person_by_id = _unique(persons, lambda x: x.person_id, "person")
    household_by_id = _unique(households, lambda x: x.household_id, "household")
    income_by_person = _unique(incomes, lambda x: x.person_id, "income")
    basket_by_key = _unique(baskets, lambda x: (x.region, x.period), "basket")
    cells = _unique(
        equivalence_cells, lambda x: (x.sex, x.age_min, x.age_max), "adult-equivalence cell"
    ).values()

    if not person_by_id or not household_by_id:
        raise PovertyInputError("persons and households must be nonempty")
    if set(income_by_person) != set(person_by_id):
        raise PovertyInputError("income mapping must cover exactly the normalized persons")
    referenced_households = {person.household_id for person in person_by_id.values()}
    if referenced_households != set(household_by_id):
        raise PovertyInputError("person-to-household mapping must cover exactly the households")
    for household in household_by_id.values():
        if household.period != contract.period:
            raise PovertyInputError("household period differs from the dependency contract")
        if not household.geography_key:
            raise PovertyInputError("household geography key must be nonempty")
        if (not math.isfinite(household.sample_weight) or household.sample_weight <= 0
                or isinstance(household.sample_weight, bool)):
            raise PovertyInputError("household sample weight must be finite and positive")

    required_baskets = {
        (region, period)
        for region in {x.region for x in household_by_id.values()}
        for period in {x.period for x in household_by_id.values()}
    }
    missing_baskets = required_baskets - set(basket_by_key)
    if missing_baskets:
        raise PovertyInputError(f"incomplete region-period basket coverage: {sorted(missing_baskets)!r}")

    cells_by_sex: dict[str, list[AdultEquivalenceCell]] = {}
    for cell in cells:
        if cell.age_min < 0 or cell.age_max < cell.age_min:
            raise PovertyInputError("adult-equivalence age intervals must be ordered and nonnegative")
        _finite_nonnegative(cell.coefficient, "adult-equivalence coefficient")
        cells_by_sex.setdefault(cell.sex, []).append(cell)
    for sex_cells in cells_by_sex.values():
        ordered = sorted(sex_cells, key=lambda x: (x.age_min, x.age_max))
        if any(right.age_min <= left.age_max for left, right in zip(ordered, ordered[1:])):
            raise PovertyInputError("adult-equivalence age intervals overlap")
    if set(cells_by_sex) != set(contract.adult_equivalence_sexes):
        raise PovertyInputError("adult-equivalence sex domains differ from the dependency contract")
    for sex in contract.adult_equivalence_sexes:
        ordered = sorted(cells_by_sex[sex], key=lambda x: x.age_min)
        boundaries = [(cell.age_min, cell.age_max) for cell in ordered]
        if (boundaries[0][0] != contract.adult_equivalence_age_min
                or boundaries[-1][1] != contract.adult_equivalence_age_max
                or any(right[0] != left[1] + 1 for left, right in zip(boundaries, boundaries[1:]))):
            raise PovertyInputError("adult-equivalence cells do not completely cover the approved age domain")

    for basket in basket_by_key.values():
        _finite_nonnegative(basket.cba, "CBA")
        _finite_nonnegative(basket.cbt, "CBT")
        if basket.cba > basket.cbt:
            raise PovertyInputError("CBA must not exceed CBT")

    result: list[PersonThreshold] = []
    for person in person_by_id.values():
        if isinstance(person.age, bool) or not isinstance(person.age, int) or person.age < 0:
            raise PovertyInputError("person age must be a nonnegative integer")
        household = household_by_id[person.household_id]
        matches = [
            cell for cell in cells_by_sex.get(person.sex, [])
            if cell.age_min <= person.age <= cell.age_max
        ]
        if len(matches) != 1:
            raise PovertyInputError(
                f"adult-equivalence coverage for person {person.person_id!r} must be exactly one cell"
            )
        income = _finite_nonnegative(income_by_person[person.person_id].amount, "linear income")
        basket = basket_by_key[(household.region, household.period)]
        coefficient = matches[0].coefficient
        person_cba = _finite_nonnegative(basket.cba * coefficient, "equivalized CBA")
        person_cbt = _finite_nonnegative(basket.cbt * coefficient, "equivalized CBT")
        result.append(PersonThreshold(
            person.person_id, person.household_id, income, coefficient,
            person_cba, person_cbt,
        ))
    return tuple(result)


def aggregate_household_thresholds(
    person_thresholds: Iterable[PersonThreshold], households: Iterable[Household]
) -> tuple[HouseholdThresholds, ...]:
    """Sum person income and equivalized baskets without statistical aggregation."""
    household_by_id = _unique(households, lambda x: x.household_id, "household")
    grouped: dict[str, list[PersonThreshold]] = {key: [] for key in household_by_id}
    for person in person_thresholds:
        if person.household_id not in grouped:
            raise PovertyInputError(f"missing household mapping: {person.household_id!r}")
        grouped[person.household_id].append(person)
    if any(not members for members in grouped.values()):
        raise PovertyInputError("every household must contain at least one person")
    result = []
    for household_id, members in grouped.items():
        household = HouseholdThresholds(
            household_id, household_by_id[household_id].region,
            household_by_id[household_id].period, household_by_id[household_id].geography_key,
            household_by_id[household_id].sample_weight, len(members),
            sum(x.income for x in members), sum(x.adult_equivalence for x in members),
            sum(x.cba for x in members), sum(x.cbt for x in members),
        )
        for field in ("income", "adult_equivalence", "cba", "cbt"):
            _finite_nonnegative(getattr(household, field), f"household {field}")
        result.append(household)
    return tuple(result)


def classify_households(
    households: Iterable[HouseholdThresholds], policies: PovertyPolicies
) -> tuple[HouseholdPoverty, ...]:
    """Apply named equality and gap-sign policies to household thresholds."""
    if not isinstance(policies, PovertyPolicies):
        raise PovertyInputError("policies must be an explicit PovertyPolicies lock value")

    def compare(income: float, threshold: float, policy: ComparisonPolicy) -> bool:
        if policy is ComparisonPolicy.BELOW:
            return income < threshold
        if policy is ComparisonPolicy.AT_OR_BELOW:
            return income <= threshold
        raise PovertyInputError(f"unsupported comparison policy: {policy!r}")

    def gap(income: float, threshold: float) -> float:
        if policies.gap_sign is GapSignPolicy.INCOME_MINUS_THRESHOLD:
            return income - threshold
        if policies.gap_sign is GapSignPolicy.THRESHOLD_MINUS_INCOME:
            return threshold - income
        raise PovertyInputError(f"unsupported gap sign policy: {policies.gap_sign!r}")

    return tuple(HouseholdPoverty(
        **household.__dict__,
        poverty=compare(household.income, household.cbt, policies.poverty_comparison),
        indigence=compare(household.income, household.cba, policies.indigence_comparison),
        poverty_gap=gap(household.income, household.cbt),
        indigence_gap=gap(household.income, household.cba),
    ) for household in households)


def calculate_household_poverty(
    persons: Iterable[NormalizedPerson], households: Iterable[Household],
    incomes: Iterable[LinearIncome], equivalence_cells: Iterable[AdultEquivalenceCell],
    baskets: Iterable[RegionalPeriodBasket], policies: PovertyPolicies,
    contract: ScientificDependencyContract,
) -> tuple[HouseholdPoverty, ...]:
    """Run the pure threshold, household-sum, and classification calculation."""
    household_records = tuple(households)
    thresholds = build_person_thresholds(
        persons, household_records, incomes, equivalence_cells, baskets, contract, policies
    )
    return classify_households(aggregate_household_thresholds(thresholds, household_records), policies)


def _validate_dependency_contract(
    contract: ScientificDependencyContract, policies: PovertyPolicies
) -> None:
    if not isinstance(contract, ScientificDependencyContract):
        raise PovertyInputError("an explicit ScientificDependencyContract is required")
    text_fields = (
        "sample_id_namespace", "period", "universe", "census_sampling_provenance",
        "census_projection_provenance", "income_release_lineage", "income_currency",
        "income_price_reference", "income_classification",
        "adult_equivalence_methodology_version", "adult_equivalence_provenance",
        "basket_provenance", "basket_currency", "basket_price_reference",
    )
    if any(not getattr(contract, field).strip() for field in text_fields):
        raise PovertyInputError("dependency contract identifiers and provenance must be nonempty")
    if contract.income_transform != "linear_ars":
        raise PovertyInputError("poverty execution requires released linear income")
    if contract.basket_unit != "currency_per_adult_equivalent":
        raise PovertyInputError("basket values must be per adult equivalent")
    if (contract.income_currency != contract.basket_currency
            or contract.income_price_reference != contract.basket_price_reference):
        raise PovertyInputError("income and baskets must share currency and price reference")
    if (not contract.adult_equivalence_sexes
            or len(set(contract.adult_equivalence_sexes)) != len(contract.adult_equivalence_sexes)
            or contract.adult_equivalence_age_min < 0
            or contract.adult_equivalence_age_max < contract.adult_equivalence_age_min):
        raise PovertyInputError("invalid approved adult-equivalence domain")
    if not policies.income_adequacy_approved:
        raise PovertyInputError("income adequacy must be explicitly approved")
    if policies.weight_use is not WeightUsePolicy.RETAIN_FOR_PUBLICATION:
        raise PovertyInputError("unsupported weight-use policy")
    if not policies.allowed_universe or policies.allowed_universe != contract.universe:
        raise PovertyInputError("policy universe differs from the Census dependency universe")
