# Stage 01 Predict

## Purpose
Generate quarter-level person-level predictions from synthetic population inputs and trained models.

## Inputs
- Synthetic population table for a given `year`
- Trained model artifacts
- Labor series inputs if employment adjustment is part of the stage
- Config values:
  - `frac`
  - `experiment_tag`
  - years / quarters

## Output
### person_predictions
- Format: `parquet`
- Filename:
  `person_predictions__q={Q}__frac={frac}__tag={experiment_tag}.parquet`

## Primary key
- `ID`
- `Q`

## Required columns
- `ID`
- `Q`
- prediction target columns, at minimum including:
  - `P47T` or model-equivalent output if log-transform is used upstream

## Invariants
- One row per `ID, Q`
- No duplicate primary keys
- Output must be reproducible from declared inputs and config
- Stage must not silently write outside configured artifact directories

## Notes
This is the prediction boundary. Downstream stages should consume its artifact, not internal notebook state.