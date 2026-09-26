# Labor bridge commissioning — L1 to L3

Status: software-ready; real-data materialization remains local.

This package replaces the historical employment-rate mutation path. The legacy
`ajustar_empleo` routine is not a scientific parent, benchmark, or fallback for
this work.

## Contracts

### L1/L2 — `research.eph-labor-truth/v1`

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

## Local L1/L2 run

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

L3 requires a harmonized Census person frame with `sample_person_id`,
`eph_agglomerate_id`, and the shared labor-model features. The located 2022/23
samples are selection-only, so this run waits for their governed full-payload
materialization plus the existing geography handoff.

After `income-modeling-eph` emits raw probabilities and an official per-domain
target table exists:

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
