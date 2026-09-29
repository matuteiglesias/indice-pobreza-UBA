# Codex — cheap real M1 timing + M3 signed-sales ENGHo run

Work in the local checkout of `matuteiglesias/indice-pobreza-UBA`.

This is a bounded execution task. Do not redesign the method, do not rerun raw EPH, do not open M2 reporting drift, and do not do non-response calibration.

## 0. Synchronize

```bash
git switch main
git pull --ff-only
make measurement-alignment-check
```

The active tree must contain:

```text
science/measurement_alignment/
tests/test_measurement_alignment.py
```

## 1. Fixed parents

Official basket parent:

```text
/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f
```

Signed-sales ENGHo Artifact B:

```text
/home/matias/data/engho-2017-18/engel-sensitivity-signed-sales/engel-sensitivity-95d0632b226c375d
```

Do not use the older clipped-sales Artifact B.

## 2. Locate existing Telescope-A household files only

Do not rerun Telescope A unless the files are genuinely absent.

Use one bounded search under `/home/matias/data` for files named `households.parquet` whose parent/output belongs to Telescope A.

Resolve exactly one file for each:

```text
2022-Q1 ... 2022-Q4
2023-Q1 ... 2023-Q4
2024-Q1 ... 2024-Q4
2025-Q1 ... 2025-Q4
```

For each candidate, verify quickly with pandas that its `period` column contains exactly the expected quarter and that it contains:

```text
household_id
basket_region
adult_equivalents
ITF
PONDIH
member_count_records
cba_per_ae
cbt_per_ae
```

Do not inspect unrelated large files.

If any quarter is missing, return only the missing quarter list and stop. Do not rebuild Telescope A automatically.

## 3. Write one real config

Create:

```text
/home/matias/data/measurement-alignment-2022-2025/config.json
```

with:

- `official_basket_release` = the fixed basket path above;
- `engel_sensitivity_release` = the signed-sales Artifact-B path above;
- `external_targets` = repository `science/measurement_alignment/external_targets/cedlas_dt370_table5.csv`;
- all 16 quarter → Telescope-A `households.parquet` paths.

## 4. Execute once

```bash
make measurement-alignment-run \
  CONFIG=/home/matias/data/measurement-alignment-2022-2025/config.json \
  OUTPUT=/home/matias/data/measurement-alignment-2022-2025/release
```

Do not modify code if it passes.

The run must fail automatically if:

- M1 T0 does not reproduce Telescope A's current-quarter lines;
- the M3 Artifact B is not signed-sales;
- M1 and M3 do not share the same official basket parent;
- any required monthly threshold cell is missing.

## 5. Required checks

Read only the compact outputs:

```text
qa.json
quarterly_estimates.csv
semester_estimates.csv
transitions.csv
external_comparison.csv
manifest.json
```

Required QA:

```text
telescope_a_baseline_reproduction = pass
m1_welfare_changed = false
m3_welfare_changed = false
m3_cba_changed = false
m2_reporting_drift = deferred
nonresponse_calibration_performed = false
```

For M1 report national person poverty FGT0 for each semester under:

```text
T0_current_quarter_mean
T1_previous_month
Tm_current_previous_midpoint
```

and the changes of T1/Tm versus T0.

For M3 report national person poverty FGT0 for each semester under:

```text
official
engho17_level_only
engho17_level_plus_trajectory
```

and the changes versus official.

Also report the external CEDLAS validation deltas already emitted by `external_comparison.csv`.

Do not average quarterly poverty rates. Use the emitted pooled-semester results.

## 6. Compact receipt only

Return:

```text
STATUS: PASS / BLOCKED

release ID
manifest SHA-256
official basket release ID
signed-sales Artifact-B release ID + manifest SHA-256

M1:
- semester T0/T1/Tm person poverty
- T1-T0 and Tm-T0 deltas
- largest quarter/semester timing effect
- count of household poverty transitions by policy

M3:
- semester official/level-only/full person poverty
- level-only and full deltas
- largest quarter/semester ENGHo effect
- count of household poverty transitions

CEDLAS validation:
- our vs published timing-midpoint deltas
- our vs published updated-consumption deltas
- descriptive only; do not tune

QA:
- all required flags

Code changes: NONE
```

If code changes become genuinely necessary, stop first and report the exact blocker instead of refactoring.

Hard stop afterward.

Do not touch predictive welfare, Census, provinces/departments, Atlas, M2 reporting drift, or non-response calibration.
