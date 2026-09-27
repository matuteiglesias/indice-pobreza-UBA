# Labor bridge commissioning — L1 to L3

Status: **L1 closed/pass; L3 implementation commissioned; bounded L2→L3 revalidation pending.**

Current work status and rerun triggers are governed by
`science/commissioning/registry.json`. This document owns the L1 truth and L3
calibration mechanics in this repository; L2 reconstruction and L4 welfare impact are owned
by `income-modeling-eph`.

This package replaces the historical employment-rate mutation path. The legacy
`ajustar_empleo` routine is not a scientific parent, benchmark, or fallback for
this work.

## Contracts

### L1 — `research.eph-labor-truth/v1`

`science/labor/core.py` and `scripts/build_eph_labor_truth.py` reconstruct the
EPH labor state directly from `ESTADO` and `PONDERA`.

For every configured quarter they emit:

- weighted and unweighted activity/employment/unemployment rates;
- complete weighted/sample accounting for `ESTADO=0/1/2/3/4`;
- official benchmark deltas in percentage points;
- one-dimensional microscope views by native agglomerate, region, sex and age
  whenever the corresponding raw columns exist.

The benchmark gate defaults to 0.10 percentage points. Official benchmark rows
remain validation-only.

The weighted headline definitions are:

```text
activity     = (weight[ESTADO=1] + weight[ESTADO=2]) / weight[all rows]
employment   = weight[ESTADO=1] / weight[all rows]
unemployment = weight[ESTADO=2] / (weight[ESTADO=1] + weight[ESTADO=2])
```

`ESTADO=0` is never silently discarded: its mass is an explicit QA output.
Groups with no economically active persons may expose activity/employment but
do not fabricate an unemployment rate.

### L3 — `research.census-labor-probabilities/v1`

`calibrate_census_domains` consumes raw Census probabilities from the
income-modeling labor bridge:

```text
p_active_raw
p_unemployed_given_active_raw
```

For every official calibration domain it solves two scalar logit offsets:

```text
mean(sigmoid(logit(p_active_raw) + alpha)) = official activity

sum(p_active * sigmoid(logit(p_u_given_active_raw) + beta)) / sum(p_active)
    = official unemployment
```

Then:

```text
p_unemployed = p_active * p_unemployed_given_active
p_employed   = p_active - p_unemployed
p_inactive   = 1 - p_active
```

Employment is implied, not separately forced; its official value is an
independent QA check.

No `design_inverse_probability_weight` is consumed. The target-year Census
sample already embeds the department target composition through the governed
selection probabilities; inverse-probability weights remain sampler design/audit
fields rather than analysis weights.

Rows outside an official calibration domain remain
`MODELLED_UNBENCHMARKED` and are never calibrated to urban EPH rates.

## Local L1 run

Create a commissioning config whose `parents.eph_person_files` maps every
quarter to the governed raw EPH person file, then run:

```bash
python scripts/build_eph_labor_truth.py \
  --config /home/matias/data/labor-bridge-config.json \
  --output /home/matias/data/eph-labor-truth-2022-2025
```

Expected first gate:

```text
16/16 quarters
benchmark_gate_status = PASS
max_abs_benchmark_delta_pp <= 0.10
```

Inspect `labor_stocks.csv` first if the gate fails, especially the
`individual_nonresponse` (`ESTADO=0`) mass.

## Local L3 run

The governed full-payload Census + semantic/geography path exists for the 2024-Q3
commissioning anchor, and L3 has already passed once on that real surface. L3 should now be
recomputed only after the bounded L2 rerun under the aligned shared-feature contract.

L3 requires a harmonized Census person frame with `sample_person_id`,
`eph_agglomerate_id`, raw labor probabilities from `income-modeling-eph`, and the exact
L1 per-domain target table:

```bash
python scripts/calibrate_census_labor_probabilities.py \
  --probabilities /home/matias/data/census-labor-raw/census_labor_probabilities_raw.parquet \
  --targets /home/matias/data/labor-targets-by-agglomerate.csv \
  --output /home/matias/data/census-labor-calibrated
```

Required QA:

- every inside-EPH domain has an explicit target;
- activity and unemployment deltas are numerical zero up to solver tolerance;
- employment is reported but not forced;
- probabilities sum to one;
- outside-EPH rows stay unbenchmarked.

## Deliberate v1 scope

Subemployment, employment demand, informality, hours and occupational category
belong to a later labor-state extension. L1 may measure them after a
period-stable microdata contract is frozen, but L3 v1 transports only the
activity/employment/unemployment core.


## L1 → L3 governed target handoff

Do not manually transcribe per-agglomerate rates. Promote the weighted native
agglomerate rows already emitted by L1:

```bash
python scripts/build_labor_calibration_targets.py \
  --microscope /home/matias/data/eph-labor-truth-2022-2025/labor_microscope.csv \
  --period 2024-Q3 \
  --output /home/matias/data/labor-targets-2024-q3.csv
```

This preserves native EPH agglomerate identity and non-rounded microdata precision.
The published national INDEC series remains the external validation gate; it is not
retyped as a calibration parent. A domain missing any of activity, employment or
unemployment fails closed rather than fabricating a target.
