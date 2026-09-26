from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator
import numpy as np
import pandas as pd

FRAME_COLUMNS = [
    "period", "period_position", "temporal_grain", "diagnostic_id", "series_id",
    "value", "unit", "universe", "geography_level", "geography_id",
    "source_role", "parent_id", "source_ref", "notes",
]


class CommissioningError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def period_position(period: str) -> float:
    q = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if q:
        return int(q.group(1)) + (int(q.group(2)) * 2 - 1) / 8
    s = re.fullmatch(r"(\d{4})-S([12])", period)
    if s:
        return int(s.group(1)) + (0.25 if s.group(2) == "1" else 0.75)
    m = re.fullmatch(r"(\d{4})-(\d{2})", period)
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)) + (int(m.group(2)) - 0.5) / 12
    raise CommissioningError(f"unsupported period label: {period!r}")


def temporal_grain(period: str) -> str:
    if "-Q" in period:
        return "quarter"
    if "-S" in period:
        return "semester"
    return "month"


def make_row(
    period: str,
    diagnostic_id: str,
    series_id: str,
    value: float,
    unit: str,
    *,
    universe: str = "",
    geography_level: str = "national",
    geography_id: str = "ARG",
    source_role: str,
    parent_id: str,
    source_ref: str = "",
    notes: str = "",
) -> dict[str, object]:
    value = float(value)
    if not math.isfinite(value):
        raise CommissioningError(f"non-finite diagnostic value: {diagnostic_id}/{series_id}")
    return {
        "period": period,
        "period_position": period_position(period),
        "temporal_grain": temporal_grain(period),
        "diagnostic_id": diagnostic_id,
        "series_id": series_id,
        "value": value,
        "unit": unit,
        "universe": universe,
        "geography_level": geography_level,
        "geography_id": geography_id,
        "source_role": source_role,
        "parent_id": parent_id,
        "source_ref": source_ref,
        "notes": notes,
    }


def require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise CommissioningError(f"{label} missing columns: {missing}")


def weighted_mean(values, weights) -> float:
    values = np.asarray(values, float)
    weights = np.asarray(weights, float)
    if (
        len(values) == 0
        or len(values) != len(weights)
        or not np.isfinite(values).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
    ):
        raise CommissioningError("invalid weighted-mean inputs")
    return float(np.average(values, weights=weights))


def weighted_quantile(values, weights, quantiles) -> np.ndarray:
    values = np.asarray(values, float)
    weights = np.asarray(weights, float)
    quantiles = np.asarray(quantiles, float)
    if (
        len(values) == 0
        or len(values) != len(weights)
        or not np.isfinite(values).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
    ):
        raise CommissioningError("invalid weighted-quantile inputs")
    order = np.argsort(values, kind="stable")
    values, weights = values[order], weights[order]
    centers = (np.cumsum(weights) - 0.5 * weights) / weights.sum()
    return np.interp(quantiles, centers, values, left=values[0], right=values[-1])


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise CommissioningError("diagnostic frame unexpectedly empty")
    require_columns(frame, FRAME_COLUMNS, "diagnostic frame")
    required = [c for c in FRAME_COLUMNS if c not in {"source_ref", "notes"}]
    bad = [c for c in required if frame[c].isna().any()]
    if bad:
        raise CommissioningError(f"diagnostic frame has null required fields: {bad}")
    key = [
        "period", "diagnostic_id", "series_id", "universe", "geography_level",
        "geography_id", "source_role", "parent_id",
    ]
    if frame.duplicated(key).any():
        raise CommissioningError("diagnostic frame has duplicate semantic rows")
    return frame.sort_values(
        ["period_position", "diagnostic_id", "series_id", "geography_id"]
    ).reset_index(drop=True)


def _set_period_ticks(
    ax, data: pd.DataFrame, *, max_ticks: int | None = None
) -> None:
    ticks = (
        data[["period_position", "period"]]
        .drop_duplicates()
        .sort_values("period_position")
    )
    if max_ticks is not None and len(ticks) > max_ticks:
        stride = math.ceil((len(ticks) - 1) / (max_ticks - 1))
        ticks = pd.concat([ticks.iloc[::stride], ticks.iloc[[-1]]]).drop_duplicates()
    ax.set_xticks(ticks.period_position, ticks.period, rotation=35, ha="right")


def plot_lines(
    data: pd.DataFrame,
    path: Path,
    title: str,
    ylabel: str,
    *,
    percent: bool = False,
    millions: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    for series, group in data.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        values = group.value.astype(float).to_numpy()
        if percent:
            values = 100 * values
        if millions:
            values = values / 1_000_000
        ax.plot(
            group.period_position.to_numpy(),
            values,
            marker="o",
            linewidth=2,
            label=series.replace("_", " "),
        )
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Period")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8, ncol=2)
    _set_period_ticks(ax, data)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _ars_log_formatter(value, _position) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if value >= 1_000:
        return f"{value / 1_000:g}k"
    return f"{value:g}"


def plot_basket_mechanics(data: pd.DataFrame, path: Path, title: str) -> None:
    levels = data[data.diagnostic_id == "basket_level"].copy()
    ratios = data[data.diagnostic_id == "basket_ratio"].copy()
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    # Nominal basket values span orders of magnitude in Argentina. A log scale
    # preserves both historical and current levels instead of flattening early years.
    for series, group in levels.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        linestyle = "--" if series.startswith("cba:") else "-"
        axes[0].plot(
            group.period_position.to_numpy(),
            group.value.astype(float).to_numpy(),
            linewidth=1.8,
            linestyle=linestyle,
            label=series.replace("_", " "),
        )
    axes[0].set_title(title)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("ARS per adult equivalent (log scale)")
    axes[0].yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    axes[0].yaxis.set_major_formatter(FuncFormatter(_ars_log_formatter))
    axes[0].grid(which="major", axis="y", alpha=0.35)
    axes[0].grid(which="minor", axis="y", alpha=0.12)
    axes[0].legend(fontsize=7, ncol=3)

    for series, group in ratios.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        axes[1].plot(
            group.period_position.to_numpy(),
            group.value.astype(float).to_numpy(),
            linewidth=1.8,
            label=series.replace("cbt_over_cba:", ""),
        )
    axes[1].set_ylabel("CBT / CBA")
    axes[1].set_xlabel("Period")
    axes[1].grid(alpha=0.2)
    axes[1].legend(fontsize=7, ncol=3)
    _set_period_ticks(axes[1], data, max_ticks=12)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_labor_reality(data: pd.DataFrame, path: Path, title: str) -> None:
    rates = data[data.diagnostic_id == "labor_rate"].copy()
    stocks = data[data.diagnostic_id == "labor_stock"].copy()
    if stocks.empty:
        plot_lines(rates, path, title, "Percent", percent=True)
        return

    fig, axes = plt.subplots(2, 1, figsize=(11, 9), sharex=True)
    for series, group in rates.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        axes[0].plot(
            group.period_position.to_numpy(),
            (100 * group.value.astype(float)).to_numpy(),
            marker="o",
            linewidth=1.8,
            label=series.replace("_", " "),
        )
    axes[0].set_title(title)
    axes[0].set_ylabel("Percent")
    axes[0].grid(alpha=0.2)
    axes[0].legend(fontsize=7, ncol=3)

    for series, group in stocks.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        axes[1].plot(
            group.period_position.to_numpy(),
            (group.value.astype(float) / 1_000_000).to_numpy(),
            marker="o",
            linewidth=1.8,
            label=series.replace("_", " "),
        )
    axes[1].set_ylabel("Millions of persons")
    axes[1].set_xlabel("Period")
    axes[1].grid(alpha=0.2)
    axes[1].legend(fontsize=8, ncol=3)
    _set_period_ticks(axes[1], data)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _one_period(data: pd.DataFrame) -> bool:
    return data.period.nunique() == 1


def plot_headline_poverty(data: pd.DataFrame, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    official = data[data.series_id.str.startswith("official:")]
    project = data[~data.series_id.str.startswith("official:")]

    for series, group in official.groupby("series_id", sort=True):
        group = group.sort_values("period_position")
        ax.plot(
            group.period_position,
            100 * group.value.astype(float),
            marker="o",
            linewidth=2.2,
            label=series.replace("_", " "),
        )
    for series, group in project.groupby("series_id", sort=True):
        ax.scatter(
            group.period_position,
            100 * group.value.astype(float),
            s=70,
            label=series.replace("_", " "),
            zorder=4,
        )

    ax.set_title(title)
    ax.set_ylabel("Percent of persons")
    ax.set_xlabel("Period")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8, ncol=2)
    _set_period_ticks(ax, data)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_welfare_cbt(data: pd.DataFrame, path: Path, title: str) -> None:
    if not _one_period(data):
        plot_lines(data, path, title, "Household welfare / CBT")
        return

    table = data.copy()
    table["stage"] = table.series_id.str.split(":").str[0]
    table["quantile"] = table.series_id.str.split(":").str[1]
    order = ["q10", "q25", "q50", "q75", "q90"]
    table["quantile"] = pd.Categorical(table.quantile, categories=order, ordered=True)
    pivot = table.pivot(index="quantile", columns="stage", values="value").reindex(order)

    fig, ax = plt.subplots(figsize=(9, 6))
    y = np.arange(len(order))
    if {"observed", "point"} <= set(pivot.columns):
        for idx, quantile in enumerate(order):
            left = float(pivot.loc[quantile, "observed"])
            right = float(pivot.loc[quantile, "point"])
            ax.plot([left, right], [idx, idx], linewidth=2, alpha=0.55)
        ax.scatter(pivot["observed"], y, s=70, label="Observed EPH")
        ax.scatter(pivot["point"], y, s=70, label="OOF point")
    else:
        for stage in pivot.columns:
            ax.scatter(pivot[stage], y, s=70, label=stage)

    ax.axvline(1.0, linewidth=1.5, linestyle="--", label="Poverty line (CBT)")
    ax.set_yticks(y, order)
    ax.set_xlabel("Household welfare / household CBT")
    ax.set_title(f"{title} — {data.period.iloc[0]}")
    ax.grid(axis="x", alpha=0.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_age_cross_section(data: pd.DataFrame, path: Path, title: str) -> None:
    if not _one_period(data):
        plot_lines(data, path, title, "Percent of persons", percent=True)
        return

    frame = data.copy()
    frame[["concept", "age_group"]] = frame.series_id.str.split(":", expand=True)
    age_order = ["0-14", "15-29", "30-64", "65+"]
    concepts = ["poverty", "indigence"]
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(age_order))
    width = 0.36
    for offset, concept in zip((-width / 2, width / 2), concepts):
        values = [
            100 * float(frame[(frame.concept == concept) & (frame.age_group == age)].value.iloc[0])
            for age in age_order
        ]
        ax.bar(x + offset, values, width=width, label=concept)
    ax.set_xticks(x, age_order)
    ax.set_ylabel("Percent of persons")
    ax.set_title(f"{title} — {data.period.iloc[0]}")
    ax.grid(axis="y", alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_region_cross_section(data: pd.DataFrame, path: Path, title: str) -> None:
    if not _one_period(data):
        plot_lines(data, path, title, "Percent of persons", percent=True)
        return

    frame = data.copy()
    frame[["concept", "region"]] = frame.series_id.str.split(":", n=1, expand=True)
    poverty = frame[frame.concept == "poverty"].copy().sort_values("value")
    regions = poverty.region.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    for ax, concept in zip(axes, ("poverty", "indigence")):
        subset = frame[frame.concept == concept].set_index("region").reindex(regions)
        ax.barh(regions, 100 * subset.value.astype(float))
        ax.set_title(concept.capitalize())
        ax.set_xlabel("Percent of persons")
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle(f"{title} — {data.period.iloc[0]}")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_telescope_b_bridge(data: pd.DataFrame, path: Path, title: str) -> None:
    if not _one_period(data):
        plot_lines(data, path, title, "Percent of persons", percent=True)
        return

    frame = data.copy()
    frame[["stage", "concept"]] = frame.series_id.str.split(":", n=1, expand=True)
    stage_order = ["observed", "oof_point", "predictive"]
    labels = ["Observed", "OOF point", "Predictive"]
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(3)
    for concept in ("poverty", "indigence"):
        subset = frame[frame.concept == concept].set_index("stage").reindex(stage_order)
        ax.plot(x, 100 * subset.value.astype(float), marker="o", linewidth=2.4, label=concept)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Percent of persons")
    ax.set_title(f"{title} — {data.period.iloc[0]}")
    ax.grid(axis="y", alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_telescope_c_bridge(data: pd.DataFrame, path: Path, title: str) -> None:
    if not _one_period(data):
        plot_lines(data, path, title, "Percent of persons", percent=True)
        return

    frame = data.copy()
    frame[["stage", "concept"]] = frame.series_id.str.split(":", n=1, expand=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    x = np.array([0, 1])
    for ax, concept in zip(axes, ("poverty", "indigence")):
        subset = frame[frame.concept == concept].set_index("stage")
        for representation in ("point", "predictive"):
            values = [
                100 * float(subset.loc[f"eph_{representation}", "value"]),
                100 * float(subset.loc[f"census_{representation}", "value"]),
            ]
            ax.plot(x, values, marker="o", linewidth=2.4, label=representation)
        ax.set_xticks(x, ["EPH", "Census target"])
        ax.set_title(concept.capitalize())
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Percent of persons")
    axes[1].legend()
    fig.suptitle(f"{title} — {data.period.iloc[0]}")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def render_figure(spec: dict, frame: pd.DataFrame, output: Path) -> dict[str, object]:
    figure_id = spec["id"]
    slug = spec["slug"]
    selectors = {
        "01": ("poverty_rate", "Percent of persons", True, False),
        "02": ("poverty_count", "Millions of persons", False, True),
        "03": ("basket_ratio", "CBT / CBA", False, False),
        "04": ("welfare_cbt_ratio_quantile", "Household welfare / CBT", False, False),
        "05": ("labor_rate", "Percent", True, False),
        "06": ("poverty_rate_age", "Percent of persons", True, False),
        "07": ("poverty_rate_region", "Percent of persons", True, False),
        "08": ("telescope_b_rate", "Percent of persons", True, False),
        "09": ("telescope_c_rate", "Percent of persons", True, False),
        "10": ("department_poverty_quantile", "Person poverty (%)", True, False),
    }
    diagnostic, ylabel, percent, millions = selectors[figure_id]
    if figure_id == "03":
        data = frame[frame.diagnostic_id.isin(["basket_level", "basket_ratio"])].copy()
    elif figure_id == "05":
        data = frame[frame.diagnostic_id.isin(["labor_rate", "labor_stock"])].copy()
    else:
        data = frame[frame.diagnostic_id == diagnostic].copy()
    if figure_id in {"01", "02"}:
        data = data[data.universe == "persons"]
    if data.empty:
        return {
            "id": figure_id,
            "slug": slug,
            "status": "blocked_missing_parent",
            "missing_diagnostics": [diagnostic],
        }

    csv_path = output / f"{figure_id}_{slug}.csv"
    png_path = output / f"{figure_id}_{slug}.png"
    data.to_csv(csv_path, index=False)
    if figure_id == "01":
        plot_headline_poverty(data, png_path, spec["title"])
    elif figure_id == "03":
        plot_basket_mechanics(data, png_path, spec["title"])
    elif figure_id == "04":
        plot_welfare_cbt(data, png_path, spec["title"])
    elif figure_id == "05":
        plot_labor_reality(data, png_path, spec["title"])
    elif figure_id == "06":
        plot_age_cross_section(data, png_path, spec["title"])
    elif figure_id == "07":
        plot_region_cross_section(data, png_path, spec["title"])
    elif figure_id == "08":
        plot_telescope_b_bridge(data, png_path, spec["title"])
    elif figure_id == "09":
        plot_telescope_c_bridge(data, png_path, spec["title"])
    else:
        plot_lines(
            data,
            png_path,
            spec["title"],
            ylabel,
            percent=percent,
            millions=millions,
        )
    return {
        "id": figure_id,
        "slug": slug,
        "status": "ready",
        "rows": int(len(data)),
        "csv": csv_path.name,
        "png": png_path.name,
        "csv_sha256": sha256(csv_path),
        "png_sha256": sha256(png_path),
        "csv_bytes": csv_path.stat().st_size,
        "png_bytes": png_path.stat().st_size,
    }
