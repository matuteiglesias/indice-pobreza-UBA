# Telescope B — same-household model bridge

## Scope

Telescope B asks one bounded question on the exact Telescope-A observed EPH cohort:

> With households, people, PONDIH weights, CBA/CBT lines, quarter and monetary units held fixed, does the poverty difference enter at the OOF point model or when the residual distribution is integrated?

It does not score Census, change baskets, refit/tune the model, or create a new poverty estimator.

## Inputs

The runner consumes:

1. Telescope-A Q3 `households.parquet`;
2. the exact raw EPH person file;
3. persisted P1-R person OOF predictions with `row_id, fold, pred`;
4. fold-specific nested household residuals with `outer_fold, residual`.

The residual table must contain the empirical household residual ECDF calibrated inside each outer training set. A single global OOF residual ECDF is intentionally insufficient for EPH evaluation.

No monetary scalar is accepted. Telescope B remains in the same nominal Q3 units and reuses Telescope-A's exact household CBA/CBT.

## B0 — identity lock

Before measurement it requires exact household/person coverage, raw sum(P47T) == Telescope-A sum_P47T == ITF, positive PONDIH, one outer fold per household, exact OOF coverage, and a nonempty nested residual ECDF for every represented outer fold.

## B1 — bridge

For the exact same households:

```text
OBSERVED:   Y_h = sum_i P47T_i
OOF POINT:  mu_h = sum_i OOF_pred_i
PREDICTIVE: Y_h = mu_h + R_(outer fold)
```

At household CBA/CBT each representation is reduced to mutually exclusive states:

```text
I   = indigent
PNI = poor non-indigent
N   = nonpoor
```

For the predictive representation:

```text
p_I   = G(CBA - mu)
p_P   = G(CBT - mu)
p_PNI = p_P - p_I
p_N   = 1 - p_P
```

The bridge is aggregated with PONDIH for households and PONDIH × member_count for persons.

## B2 — exact residual-flow decomposition

For threshold z:

```text
q_h = 1(mu_h <= z_h)
p_h = G(z_h - mu_h)
```

Telescope B reports downward crossing mass, upward crossing mass and net predictive-minus-point movement, and verifies exactly:

```text
downward - upward = predictive - point
```

No simulation is required for FGT0.

## B3 — bounded reliability diagnostic

At the actual household-specific CBA and CBT, predicted probabilities are sorted into weighted equal-mass bins. For household- and person-weighted views it records mean predicted probability, observed event rate, weight mass and household count, plus weighted Brier scores.

This is intentionally not a general calibration program.

## Outputs

```text
households.parquet
bridge.csv
flows.csv
point_transitions.csv
threshold_calibration.csv
summary.json
report.md
```

## Deferred

PIT, predictive interval coverage, conditional/heteroskedastic residual ECDFs, P2 model arms, FGT1/FGT2, Census transport and multi-quarter validation are deferred unless B1/B2 show that the residual layer is the material failure.
