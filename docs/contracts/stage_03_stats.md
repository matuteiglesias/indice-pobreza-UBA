# Stage 03 Stats

## Purpose
Aggregate household poverty outputs into tabular indicators by universe and grouping dimensions.

## Inputs
- `stage_02_poverty.household_poverty`
- optional `stage_02_poverty.household_geo` when grouping needs location
- CPI or current-peso adjustment inputs if configured

## Outputs
### stats_table
- Format: `parquet`
- Filename:
  `stats__base={base}__groupby={groupby}__frac={frac}__tag={experiment_tag}.parquet`

### stats_jsonl
- Format: `jsonl`
- Filename:
  `stats__base={base}__groupby={groupby}__frac={frac}__tag={experiment_tag}.jsonl`

## Primary key
No single universal primary key is enforced at file level.
Recommended uniqueness key:
- `Q`
- `base`
- grouping columns
- `observable`
- `synthetic_stat`

## Required columns
- `Q`
- `base`
- grouping columns requested by config
- `observable`
- `synthetic_stat`
- `value`

## Invariants
- Stage should be idempotent for a given config and inputs
- Re-running should not duplicate rows in canonical outputs
- Nested JSON is not canonical storage; it may be materialized later from table outputs