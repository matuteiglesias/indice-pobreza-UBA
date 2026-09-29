# Codex — bounded real CEDLAS DT370 forensic replication

This handoff runs the already-implemented forensic comparison. It does not redesign the method and does not tune anything to match CEDLAS.

## Fixed governed parents

ENGHo:

```text
/home/matias/data/engho-2017-18/releases/engho-2017-2018-ff05578d65ae
```

Regional IPC:

```text
/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f
```

Official baskets:

```text
/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f
```

Primary signed-sales p29-p48 Artifact B:

```text
/home/matias/data/engho-2017-18/engel-sensitivity-signed-sales/engel-sensitivity-95d0632b226c375d
```

Do not use the older clipped-sales artifact.

## A. Canastas threshold-side forensic lane

Work in local `canastasINDEC`:

```bash
git switch main
git pull --ff-only
make cedlas-dt370-test
```

Create one work root:

```bash
ROOT=/home/matias/data/cedlas-dt370-forensic
mkdir -p "$ROOT"
```

### A1. Low-education provenance

```bash
make cedlas-dt370-provenance \
  ENGHO_RELEASE=/home/matias/data/engho-2017-18/releases/engho-2017-2018-ff05578d65ae \
  CEDLAS_PROVENANCE_OUTPUT="$ROOT/provenance"
```

This must emit aggregate-only outputs. No respondent-level records may be copied.

Read only:

```text
provenance/qa.json
provenance/national_reference_variants.csv
provenance/regional_reference_variants.csv
provenance/division02_split_summary.json
```

### A2. Paper-exact threshold replication

```bash
make cedlas-dt370-build \
  ENGEL_IPC_RELEASE=/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f \
  ENGEL_OFFICIAL_BASKET_RELEASE=/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f \
  CEDLAS_OUTPUT="$ROOT/threshold"
```

Capture the immutable nested release path printed by the command as `CEDLAS_THRESHOLD_RELEASE`.

Then:

```bash
make cedlas-dt370-check RELEASE_DIR="$CEDLAS_THRESHOLD_RELEASE"

make cedlas-dt370-commission \
  RELEASE_DIR="$CEDLAS_THRESHOLD_RELEASE" \
  CEDLAS_COMMISSION_OUTPUT="$ROOT/threshold-commissioning"
```

Required paper-exact specification:

```text
food = COICOP01 + full COICOP02
tobacco_in_food = true
reference vector = published equal average of low and very-low education groups
regionalization = published inherited old ICE ratios
base = 2018-05
```

Report Table 3 and Table 4 validation.

### A3. Old-method reconstruction control

```bash
make cedlas-dt370-old-reconstruction \
  ENGEL_IPC_RELEASE=/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f \
  ENGEL_OFFICIAL_BASKET_RELEASE=/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f \
  CEDLAS_OLD_OUTPUT="$ROOT/old-method"
```

This is diagnostic only. Do not tune the new method to reduce this reconstruction error.

### A4. Method-choice threshold attribution

```bash
make cedlas-dt370-choice-attribution \
  CEDLAS_PROVENANCE_OUTPUT="$ROOT/provenance" \
  ENGEL_IPC_RELEASE=/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f \
  ENGEL_OFFICIAL_BASKET_RELEASE=/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f \
  CEDLAS_CHOICE_OUTPUT="$ROOT/choices"
```

Capture the immutable nested choice release as `CEDLAS_CHOICE_RELEASE`.

The variants must include:

```text
paper_exact
paper_vector_alcohol_only
microdata_equal_inherited_full02
microdata_pooled_inherited_full02
microdata_equal_direct_full02
microdata_pooled_direct_full02
microdata_equal_direct_alcohol_only
microdata_pooled_direct_alcohol_only
```

## B. Poverty-side observed-EPH replication

Work in local `indice-pobreza-UBA`:

```bash
git switch main
git pull --ff-only
make cedlas-dt370-replication-check
make cedlas-choice-attribution-check
```

### B1. Reuse the existing 16 Telescope-A household files

Do not rerun Telescope A.

Resolve exactly one existing `households.parquet` for every quarter 2022-Q1 through 2025-Q4 under `/home/matias/data`.

Each must have the exact expected `period` and the columns:

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

If any quarter is absent, stop and report only the missing quarters.

### B2. Paper-exact Table-5 replication

Create `$ROOT/poverty-paper-config.json` containing:

- `cedlas_replication_release` = `CEDLAS_THRESHOLD_RELEASE`;
- the standard repository CEDLAS Table-5 external target file;
- all 16 quarter/Telescope-A household paths.

Then:

```bash
make cedlas-dt370-replication-run \
  CONFIG="$ROOT/poverty-paper-config.json" \
  OUTPUT="$ROOT/poverty-paper"
```

Acceptance target:

```text
max |our updated-consumption poverty - CEDLAS Table 5| <= 0.1 percentage point
```

If this fails, do not tune. Report the first upstream layer that failed:

```text
Table 1 structure
Table 3 regionalization
Table 4 ICE path
or Table 5 poverty application
```

### B3. Full choice attribution in poverty points

Create `$ROOT/poverty-choice-config.json` with:

- `cedlas_choice_release` = `CEDLAS_CHOICE_RELEASE`;
- `primary_engel_sensitivity_release` = the fixed signed-sales p29-p48 Artifact B;
- external targets;
- the same 16 Telescope-A household files.

Then:

```bash
make cedlas-choice-attribution-run \
  CONFIG="$ROOT/poverty-choice-config.json" \
  OUTPUT="$ROOT/poverty-choices"
```

Read only compact outputs:

```text
qa.json
choice_attribution.csv
semester_estimates.csv
transitions.csv
manifest.json
```

## Final compact return

Return:

1. Paper-exact threshold release ID + manifest SHA.
2. Table-3 max share/ICE mismatch.
3. Table-4 max ICE mismatch.
4. Low-education provenance:
   - very-low Table-1 max pp difference;
   - low Table-1 max pp difference;
   - equal-group microdata vs published combined max pp difference;
   - pooled vs equal-group maximum pp difference;
   - pooled/equal alcohol fraction of division 02.
5. Old-method reconstruction max absolute/relative ICE discrepancy.
6. Table-5 semester results and max absolute poverty mismatch in pp.
7. For every forensic variant, semester poverty and:
   - delta vs `paper_exact`;
   - delta vs `primary_p29_p48_full`.
8. A compact attribution conclusion:
   - reference-population construction effect;
   - equal-group vs pooled effect;
   - tobacco/full-02 food-scope effect;
   - inherited-vs-direct regionalization effect;
   - residual price-path/reconstruction effect.
9. PASS / DIAGNOSTIC_MISMATCH.

Do not alter the primary p29-p48 Artifact A/B.
Do not calculate M2 reporting drift.
Do not do non-response calibration.
Do not touch predictive welfare, Census, provinces/departments, or Atlas.
Do not change code unless an actual implementation bug blocks the already-defined run.
