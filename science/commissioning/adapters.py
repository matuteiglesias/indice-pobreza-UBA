from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from core import (
    CommissioningError,
    make_row,
    require_columns,
    sha256,
    validate_frame,
    weighted_mean,
    weighted_quantile,
)

ROOT = Path(__file__).resolve().parent
BENCHMARKS = ROOT / "benchmarks"
REGIONS = {
    "gran_buenos_aires", "noroeste", "noreste", "cuyo", "pampeana", "patagonia"
}
AGE_GROUPS = (
    ("0-14", 0, 14),
    ("15-29", 15, 29),
    ("30-64", 30, 64),
    ("65+", 65, 200),
)


def benchmark_rows() -> list[dict[str, object]]:
    sources = json.loads((BENCHMARKS / "sources.json").read_text())["sources"]
    rows: list[dict[str, object]] = []

    poverty = pd.read_csv(BENCHMARKS / "indec_poverty_semester.csv")
    require_columns(
        poverty,
        ["period", "universe", "concept", "rate", "count", "source_id"],
        "poverty benchmark",
    )
    for item in poverty.itertuples():
        source = sources[item.source_id]
        rows.append(
            make_row(
                item.period,
                "poverty_rate",
                f"official:{item.concept}",
                item.rate,
                "proportion",
                universe=item.universe,
                source_role="external_validation_benchmark",
                parent_id=item.source_id,
                source_ref=source["url"],
                notes="INDEC 31-agglomerate EPH benchmark; validation only",
            )
        )
        rows.append(
            make_row(
                item.period,
                "poverty_count",
                f"official:{item.concept}",
                item.count,
                item.universe,
                universe=item.universe,
                source_role="external_validation_benchmark",
                parent_id=item.source_id,
                source_ref=source["url"],
                notes="INDEC exact published count; validation only",
            )
        )

    labor = pd.read_csv(BENCHMARKS / "indec_labor_quarter.csv")
    require_columns(
        labor,
        ["period", "activity_rate", "employment_rate", "unemployment_rate", "source_id"],
        "labor benchmark",
    )
    for item in labor.itertuples():
        source = sources[item.source_id]
        for metric in ("activity", "employment", "unemployment"):
            rows.append(
                make_row(
                    item.period,
                    "labor_rate",
                    f"official:{metric}",
                    getattr(item, f"{metric}_rate"),
                    "proportion",
                    universe="persons",
                    source_role="external_validation_benchmark",
                    parent_id=item.source_id,
                    source_ref=source["url"],
                    notes="INDEC headline rate, total 31 agglomerates",
                )
            )
    return rows


def basket_rows(cba_path: Path, cbt_path: Path) -> list[dict[str, object]]:
    cba, cbt = pd.read_csv(cba_path), pd.read_csv(cbt_path)
    date_candidates = ("indice_tiempo", "period", "date", "Fecha")
    cba_date = next((c for c in date_candidates if c in cba), None)
    cbt_date = next((c for c in date_candidates if c in cbt), None)
    if not cba_date or not cbt_date:
        raise CommissioningError("basket files need an explicit date column")
    cba["_date"] = pd.to_datetime(cba[cba_date], errors="coerce")
    cbt["_date"] = pd.to_datetime(cbt[cbt_date], errors="coerce")
    if cba._date.isna().any() or cbt._date.isna().any():
        raise CommissioningError("basket files contain invalid dates")
    shared = sorted(REGIONS & set(cba.columns) & set(cbt.columns))
    if set(shared) != REGIONS:
        raise CommissioningError(
            f"basket files must expose six canonical regions, got {shared}"
        )

    left = cba.melt(
        id_vars="_date",
        value_vars=shared,
        var_name="region",
        value_name="cba",
    )
    right = cbt.melt(
        id_vars="_date",
        value_vars=shared,
        var_name="region",
        value_name="cbt",
    )
    merged = left.merge(right, on=["_date", "region"], validate="one_to_one")
    merged = merged.rename(columns={"_date": "date"})
    merged["cba"] = pd.to_numeric(merged.cba, errors="coerce")
    merged["cbt"] = pd.to_numeric(merged.cbt, errors="coerce")
    if (
        merged[["cba", "cbt"]].isna().any().any()
        or (merged.cba <= 0).any()
        or (merged.cbt < merged.cba).any()
    ):
        raise CommissioningError("invalid basket values")

    out = []
    parent = f"{cba_path.name}+{cbt_path.name}"
    for item in merged.itertuples():
        period = item.date.strftime("%Y-%m")
        out.extend(
            [
                make_row(
                    period,
                    "basket_level",
                    f"cba:{item.region}",
                    item.cba,
                    "ARS_per_adult_equivalent",
                    geography_level="poverty_region",
                    geography_id=item.region,
                    source_role="poverty_line_parent",
                    parent_id=parent,
                ),
                make_row(
                    period,
                    "basket_level",
                    f"cbt:{item.region}",
                    item.cbt,
                    "ARS_per_adult_equivalent",
                    geography_level="poverty_region",
                    geography_id=item.region,
                    source_role="poverty_line_parent",
                    parent_id=parent,
                ),
                make_row(
                    period,
                    "basket_ratio",
                    f"cbt_over_cba:{item.region}",
                    item.cbt / item.cba,
                    "ratio",
                    geography_level="poverty_region",
                    geography_id=item.region,
                    source_role="deterministic_diagnostic",
                    parent_id=parent,
                    notes="CBT/CBA; inverse Engel-coefficient presentation diagnostic",
                ),
            ]
        )
    return out


def eph_labor_rows(period: str, path: Path) -> list[dict[str, object]]:
    frame = pd.read_csv(
        path,
        sep=";",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    require_columns(frame, ["ESTADO", "PONDERA"], f"EPH persons {period}")
    state = pd.to_numeric(frame.ESTADO, errors="coerce")
    weight = pd.to_numeric(frame.PONDERA, errors="coerce")
    if state.isna().any() or weight.isna().any() or (weight < 0).any():
        raise CommissioningError(f"invalid ESTADO/PONDERA in {period}")
    total = float(weight.sum())
    if total <= 0:
        raise CommissioningError(f"non-positive EPH population weight in {period}")

    stocks = {
        "employed": float(weight[state == 1].sum()),
        "unemployed": float(weight[state == 2].sum()),
        "inactive": float(weight[state == 3].sum()),
    }
    pea = stocks["employed"] + stocks["unemployed"]
    if pea <= 0:
        raise CommissioningError(f"non-positive EPH economically active population in {period}")
    rates = {
        "activity": pea / total,
        "employment": stocks["employed"] / total,
        "unemployment": stocks["unemployed"] / pea,
    }
    out = []
    for metric, value in stocks.items():
        out.append(
            make_row(
                period,
                "labor_stock",
                f"eph_reconstructed:{metric}",
                value,
                "persons",
                universe="persons",
                source_role="EPH_microdata_diagnostic",
                parent_id=path.name,
                notes="PONDERA-weighted; ESTADO 1 occupied, 2 unemployed, 3 inactive",
            )
        )
    for metric, value in rates.items():
        out.append(
            make_row(
                period,
                "labor_rate",
                f"eph_reconstructed:{metric}",
                value,
                "proportion",
                universe="persons",
                source_role="EPH_microdata_diagnostic",
                parent_id=path.name,
            )
        )
    return out


def telescope_a_rows(
    period: str,
    directory: Path,
    eph_person_path: Path | None,
) -> list[dict[str, object]]:
    summary_path = directory / "summary.json"
    households_path = directory / "households.parquet"
    if not summary_path.exists() or not households_path.exists():
        raise CommissioningError(f"Telescope A directory incomplete: {directory}")

    summary = json.loads(summary_path.read_text())
    households = pd.read_parquet(households_path)
    out: list[dict[str, object]] = []

    for item in summary.get("national_estimates", []):
        if item.get("universe") == "persons" and item.get("estimand") == "fgt0":
            out.append(
                make_row(
                    period,
                    "poverty_rate",
                    f"eph_observed:{item['concept']}",
                    item["estimate"],
                    "proportion",
                    universe="persons",
                    source_role="telescope_a",
                    parent_id=directory.name,
                )
            )

    for item in summary.get("regional_estimates", []):
        if item.get("universe") == "persons" and item.get("estimand") == "fgt0":
            out.append(
                make_row(
                    period,
                    "poverty_rate_region",
                    f"{item['concept']}:{item['geography_id']}",
                    item["estimate"],
                    "proportion",
                    universe="persons",
                    geography_level=item.get("geography_level", "eph_region"),
                    geography_id=item["geography_id"],
                    source_role="telescope_a",
                    parent_id=directory.name,
                )
            )

    require_columns(
        households,
        ["ITF", "household_cbt", "PONDIH", "member_count_records"],
        "Telescope A households",
    )
    ratio = households.ITF.astype(float) / households.household_cbt.astype(float)
    weights = (
        households.PONDIH.astype(float)
        * households.member_count_records.astype(float)
    )
    quantiles = (0.10, 0.25, 0.50, 0.75, 0.90)
    for q, value in zip(
        quantiles,
        weighted_quantile(ratio, weights, quantiles),
    ):
        out.append(
            make_row(
                period,
                "welfare_cbt_ratio_quantile",
                f"observed:q{int(q * 100):02d}",
                value,
                "ratio",
                universe="persons",
                source_role="telescope_a",
                parent_id=directory.name,
            )
        )

    if eph_person_path is not None:
        people = pd.read_csv(
            eph_person_path,
            sep=";",
            dtype=str,
            keep_default_na=False,
            low_memory=False,
        )
        require_columns(
            people,
            ["CODUSU", "NRO_HOGAR", "ANO4", "TRIMESTRE", "CH06"],
            f"EPH age {period}",
        )
        people["household_id"] = (
            people.ANO4.str.strip()
            + ":"
            + people.TRIMESTRE.str.strip()
            + ":"
            + people.CODUSU.str.strip()
            + ":"
            + people.NRO_HOGAR.str.strip()
        )
        age = pd.to_numeric(people.CH06, errors="coerce").mask(lambda x: x == -1, 0)
        people["age"] = age
        require_columns(
            households,
            ["household_id", "PONDIH", "poor", "indigent"],
            "Telescope A state surface",
        )
        joined = people.merge(
            households[["household_id", "PONDIH", "poor", "indigent"]].rename(
                columns={"PONDIH": "household_PONDIH"}
            ),
            on="household_id",
            how="inner",
            validate="many_to_one",
        )
        if joined.age.isna().any():
            raise CommissioningError(
                f"missing age in retained Telescope-A persons for {period}"
            )
        joined["household_PONDIH"] = pd.to_numeric(
            joined.household_PONDIH, errors="coerce"
        )
        for label, lo, hi in AGE_GROUPS:
            group = joined[(joined.age >= lo) & (joined.age <= hi)]
            if group.empty:
                raise CommissioningError(f"empty age group {label} in {period}")
            for concept, column in (("poverty", "poor"), ("indigence", "indigent")):
                estimate = weighted_mean(
                    group[column].astype(float),
                    group.household_PONDIH,
                )
                out.append(
                    make_row(
                        period,
                        "poverty_rate_age",
                        f"{concept}:{label}",
                        estimate,
                        "proportion",
                        universe="persons",
                        geography_level="age_group",
                        geography_id=label,
                        source_role="telescope_a_grouped_view",
                        parent_id=directory.name,
                        notes="Existing household state inherited by persons; no new classification",
                    )
                )
    return out


def telescope_b_rows(period: str, directory: Path) -> list[dict[str, object]]:
    bridge_path = directory / "bridge.csv"
    if not bridge_path.exists():
        raise CommissioningError(f"Telescope B bridge missing: {bridge_path}")
    bridge = pd.read_csv(bridge_path)
    require_columns(
        bridge,
        ["stage", "universe", "state", "estimate"],
        "Telescope B bridge",
    )
    people = bridge[bridge.universe == "persons"].copy()
    out = []
    for stage in ("OBSERVED", "OOF_POINT", "PREDICTIVE"):
        subset = people[people.stage == stage].set_index("state")
        expected = {"indigent", "poor_non_indigent", "nonpoor"}
        if not expected <= set(subset.index):
            raise CommissioningError(
                f"Telescope B missing person states for {stage}"
            )
        values = {
            "indigence": float(subset.loc["indigent", "estimate"]),
            "poverty": float(
                subset.loc["indigent", "estimate"]
                + subset.loc["poor_non_indigent", "estimate"]
            ),
        }
        for concept, value in values.items():
            out.append(
                make_row(
                    period,
                    "telescope_b_rate",
                    f"{stage.lower()}:{concept}",
                    value,
                    "proportion",
                    universe="persons",
                    source_role="telescope_b",
                    parent_id=directory.name,
                )
            )

    households_path = directory / "households.parquet"
    if households_path.exists():
        households = pd.read_parquet(households_path)
        require_columns(
            households,
            ["point_welfare", "household_cbt", "PONDIH", "member_count_records"],
            "Telescope B households",
        )
        ratio = (
            households.point_welfare.astype(float)
            / households.household_cbt.astype(float)
        )
        weights = (
            households.PONDIH.astype(float)
            * households.member_count_records.astype(float)
        )
        quantiles = (0.10, 0.25, 0.50, 0.75, 0.90)
        for q, value in zip(
            quantiles,
            weighted_quantile(ratio, weights, quantiles),
        ):
            out.append(
                make_row(
                    period,
                    "welfare_cbt_ratio_quantile",
                    f"point:q{int(q * 100):02d}",
                    value,
                    "ratio",
                    universe="persons",
                    source_role="telescope_b",
                    parent_id=directory.name,
                )
            )
    return out


def telescope_c_rows(period: str, directory: Path) -> list[dict[str, object]]:
    path = directory / "transport_decomposition.csv"
    if not path.exists():
        raise CommissioningError(f"Telescope C decomposition missing: {path}")
    frame = pd.read_csv(path).set_index("state")
    expected = {"indigent", "poor_non_indigent", "nonpoor"}
    if not expected <= set(frame.index):
        raise CommissioningError("Telescope C decomposition missing I/PNI/N")

    out = []
    for stage in (
        "eph_point",
        "eph_predictive",
        "census_point",
        "census_predictive",
    ):
        values = {
            "indigence": float(frame.loc["indigent", stage]),
            "poverty": float(
                frame.loc["indigent", stage]
                + frame.loc["poor_non_indigent", stage]
            ),
        }
        for concept, value in values.items():
            out.append(
                make_row(
                    period,
                    "telescope_c_rate",
                    f"{stage}:{concept}",
                    value,
                    "proportion",
                    universe="persons",
                    source_role="telescope_c",
                    parent_id=directory.name,
                )
            )

    concepts = {
        "indigence": ["indigent"],
        "poverty": ["indigent", "poor_non_indigent"],
    }
    for concept, states in concepts.items():
        for metric in (
            "point_transport",
            "predictive_transport",
            "transport_x_residual_interaction",
        ):
            out.append(
                make_row(
                    period,
                    "telescope_c_delta",
                    f"{metric}:{concept}",
                    float(frame.loc[states, metric].sum()),
                    "proportion",
                    universe="persons",
                    source_role="telescope_c",
                    parent_id=directory.name,
                )
            )
    return out


def poverty_release_rows(period: str, directory: Path) -> list[dict[str, object]]:
    path = directory / "poverty_estimates.csv"
    if not path.exists():
        raise CommissioningError(f"poverty release fact table missing: {path}")
    facts = pd.read_csv(path, dtype={"geography_id": str})
    require_columns(
        facts,
        [
            "estimation_period",
            "universe",
            "geography_level",
            "geography_id",
            "concept",
            "estimand",
            "estimate",
            "weighted_denominator",
        ],
        "poverty release",
    )
    periods = set(facts.estimation_period.astype(str))
    if periods != {period}:
        raise CommissioningError(
            f"poverty release period mismatch {periods} != {period}"
        )

    out = []
    national = facts[
        (facts.universe == "persons")
        & (facts.geography_level == "national")
        & (facts.estimand == "fgt0")
    ]
    for item in national.itertuples():
        out.append(
            make_row(
                period,
                "poverty_rate",
                f"released_target:{item.concept}",
                item.estimate,
                "proportion",
                universe="persons",
                source_role="poverty_estimate_release",
                parent_id=directory.name,
            )
        )

    departments = facts[
        (facts.universe == "persons")
        & (facts.geography_level == "department_2010")
        & (facts.concept == "poverty")
        & (facts.estimand == "fgt0")
    ].copy()
    if not departments.empty:
        if departments.geography_id.duplicated().any():
            raise CommissioningError(
                f"duplicate department poverty fact in {period}"
            )
        values = pd.to_numeric(departments.estimate, errors="coerce")
        weights = pd.to_numeric(
            departments.weighted_denominator,
            errors="coerce",
        )
        if (
            values.isna().any()
            or weights.isna().any()
            or (weights <= 0).any()
        ):
            raise CommissioningError(
                f"invalid department estimate/denominator in {period}"
            )
        quantiles = (0.10, 0.25, 0.50, 0.75, 0.90)
        for q, value in zip(
            quantiles,
            weighted_quantile(values, weights, quantiles),
        ):
            out.append(
                make_row(
                    period,
                    "department_poverty_quantile",
                    f"q{int(q * 100):02d}",
                    value,
                    "proportion",
                    universe="persons",
                    geography_level="department_2010",
                    geography_id="distribution",
                    source_role="poverty_release_descriptive_view",
                    parent_id=directory.name,
                    notes="Weighted by released person denominator; descriptive diagnostic only",
                )
            )
    return out


def parent_identity(path_string: str | None) -> dict[str, object] | None:
    if not path_string:
        return None
    path = Path(path_string).expanduser().resolve()
    item: dict[str, object] = {
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        return item
    if path.is_file():
        item.update(
            {
                "kind": "file",
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
        return item

    item["kind"] = "directory"
    evidence = {}
    for name in (
        "release_manifest.json",
        "manifest.json",
        "summary.json",
        "checksums.sha256",
        "bridge.csv",
        "transport_decomposition.csv",
    ):
        candidate = path / name
        if candidate.exists() and candidate.is_file():
            evidence[name] = {
                "sha256": sha256(candidate),
                "bytes": candidate.stat().st_size,
            }
    item["evidence"] = evidence
    return item


def build_frame(
    config: dict,
) -> tuple[pd.DataFrame, dict[str, object], list[dict[str, str]]]:
    rows = benchmark_rows()
    errors: list[dict[str, str]] = []
    parents = config.get("parents", {})
    manifest_parents: dict[str, object] = {}

    def capture(label: str, function, *args) -> None:
        try:
            rows.extend(function(*args))
        except Exception as exc:
            errors.append(
                {
                    "adapter": label,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    cba = parents.get("basket_cba_csv")
    cbt = parents.get("basket_cbt_csv")
    manifest_parents["basket_cba_csv"] = parent_identity(cba)
    manifest_parents["basket_cbt_csv"] = parent_identity(cbt)
    if cba and cbt:
        capture("baskets", basket_rows, Path(cba), Path(cbt))

    eph_files = parents.get("eph_person_files", {}) or {}
    manifest_parents["eph_person_files"] = {
        period: parent_identity(path)
        for period, path in eph_files.items()
    }
    for period, path in eph_files.items():
        capture(
            f"eph_labor:{period}",
            eph_labor_rows,
            period,
            Path(path),
        )

    telescope_a = parents.get("telescope_a", {}) or {}
    telescope_b = parents.get("telescope_b", {}) or {}
    telescope_c = parents.get("telescope_c", {}) or {}
    releases = parents.get("poverty_releases", {}) or {}

    manifest_parents["telescope_a"] = {
        period: parent_identity(path)
        for period, path in telescope_a.items()
    }
    manifest_parents["telescope_b"] = {
        period: parent_identity(path)
        for period, path in telescope_b.items()
    }
    manifest_parents["telescope_c"] = {
        period: parent_identity(path)
        for period, path in telescope_c.items()
    }
    manifest_parents["poverty_releases"] = {
        period: parent_identity(path)
        for period, path in releases.items()
    }

    for period, path in telescope_a.items():
        capture(
            f"telescope_a:{period}",
            telescope_a_rows,
            period,
            Path(path),
            Path(eph_files[period]) if period in eph_files else None,
        )
    for period, path in telescope_b.items():
        capture(
            f"telescope_b:{period}",
            telescope_b_rows,
            period,
            Path(path),
        )
    for period, path in telescope_c.items():
        capture(
            f"telescope_c:{period}",
            telescope_c_rows,
            period,
            Path(path),
        )
    for period, path in releases.items():
        capture(
            f"poverty_release:{period}",
            poverty_release_rows,
            period,
            Path(path),
        )

    frame = validate_frame(pd.DataFrame(rows))
    return frame, manifest_parents, errors
