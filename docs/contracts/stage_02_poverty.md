# Stage 02 Poverty

## Purpose
Transform person-level predictions into household-level poverty and indigence metrics, including geographic enrichment.

## Inputs
- `stage_01_predict.person_predictions`
- Synthetic population base data
- Adult equivalence reference
- Basket / CPI / region lookup tables
- Geographic lookup tables

## Outputs
### person_income
- Format: `parquet`
- Filename:
  `person_income__q={Q}__frac={frac}__tag={experiment_tag}.parquet`

### household_poverty
- Format: `parquet`
- Filename:
  `household_poverty__q={Q}__frac={frac}__tag={experiment_tag}.parquet`

### household_geo
- Format: `parquet`
- Filename:
  `household_geo__q={Q}__frac={frac}__tag={experiment_tag}.parquet`

## Primary keys
- `person_income`: `ID`, `Q`
- `household_poverty`: `HOGAR_REF_ID`, `Q`
- `household_geo`: `HOGAR_REF_ID`, `Q`

## Required columns
### person_income
- `ID`
- `Q`
- person income column

### household_poverty
- `HOGAR_REF_ID`
- `Q`
- `P47T_hogar`
- `CB_EQUIV`
- `CBA`
- `CBT`
- `Pobreza`
- `Indigencia`

### household_geo
- `HOGAR_REF_ID`
- `Q`
- geographic join keys needed by stage 04

## Invariants
- No duplicate primary keys
- Household poverty rows must be one per household-quarter
- Poverty flags must be derivable from declared thresholds and household income columns