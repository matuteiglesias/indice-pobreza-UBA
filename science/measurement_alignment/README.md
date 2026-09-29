# Measurement Alignment — M1 timing + M3 ENGHo/Engel

This family sits beside Telescope A. It never rewrites Telescope A's canonical A0.

## Frozen scope

- study window: 2022-Q1 through 2025-Q4;
- welfare: Telescope-A A0 observed household ITF, unchanged;
- weights: source PONDIH, unchanged;
- adult equivalence: Telescope-A audited adult equivalents, unchanged;
- M1 changes threshold timing only;
- M3 changes CBT/ICE only through the signed-sales ENGHo Artifact B;
- M2 reporting drift is deferred;
- income non-response calibration is out of scope.

## M1 timing policies

Because the quarter-native EPH surface does not identify an exact household receipt/spending month, these are deterministic timing sensitivities, not claims about household-specific timing.

For each region and quarter with current months m1,m2,m3:

- T0_current_quarter_mean: mean of the three current monthly CBA/CBT observations; must reproduce Telescope A's incumbent line.
- T1_previous_month: mean of lines for m1-1, m2-1, m3-1.
- Tm_current_previous_midpoint: 0.5 × T0 + 0.5 × T1.

Nothing else moves.

## M3 ENGHo/Engel policies

Consume only research.argentina-regional-baskets-engel-sensitivity/v1 whose locked Artifact-A parent uses:

research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2

Quarter lines are arithmetic means of the three Artifact-B monthly paths:

- official;
- engHo17_level_only;
- engHo17_level_plus_trajectory.

Official CBA remains unchanged, so M3 affects poverty/CBT but not the nutritional CBA definition.

## Estimation

The runner consumes Telescope A households.parquet, so it reuses the exact audited A0 cohort and does not re-parse raw EPH. It recomputes household/person FGT0/FGT1/FGT2 using PONDIH and PONDIH × household members respectively.

Semester estimates pool the two quarter-level household contribution tables and recompute weighted estimands. Quarterly poverty rates are never averaged to manufacture a semester.

## External evidence

external_targets/cedlas_dt370_table5.csv is validation evidence only. It does not tune lines or estimator parameters. Our M3 reference population and regional construction deliberately differ from CEDLAS, and M1 is quarter-native rather than household-month exact.
