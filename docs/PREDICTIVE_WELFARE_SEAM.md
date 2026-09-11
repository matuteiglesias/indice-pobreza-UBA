# Predictive welfare -> Poverty research seam

Status: experimental cross-repo integration.

This seam preserves the science established by `encuestador-de-hogares` Q7/Q8 instead of reducing Census welfare to a point estimate.

## Upstream predictive welfare contract

Target artifact:

```text
research.household-welfare-predictive/v1
```

First representation:

```text
Y_h = max(0, point_welfare_h + R)
```

where `R` is a governed empirical household residual ECDF calibrated only from EPH out-of-fold household predictions.

The artifact owns:

- frame namespace;
- welfare period;
- currency / monetary reference;
- welfare concept `household_total_family_income`;
- household point welfare locations;
- the shared empirical residual distribution;
- support policy `floor_at_zero`;
- calibration/model/source lineage;
- transport/support diagnostics.

Poverty does **not** import or fit the upstream model.

## Predictive measurement

For household poverty line `L` and empirical predictive welfare draws `w_j`, Poverty computes:

```text
FGT0 = mean(w_j <= L)
FGT1 = mean(max((L - w_j) / L, 0))
FGT2 = mean(max((L - w_j) / L, 0) ** 2)
```

The implementation in `science/predictive_measurement.py` evaluates the exact empirical quantities from the sorted residual ECDF and prefix moments, avoiding an explicit household x residual draw matrix.

The same operation is performed separately for household CBA and CBT after applying the existing adult-equivalence method.

## Why marginal distributions suffice for point FGT estimates

Population FGT point estimands are averages of household contributions. By linearity of expectation, expected household FGT contributions can be aggregated without specifying cross-household dependence in predictive welfare.

This does **not** provide a defensible variance or confidence interval for the aggregate. Until an approved joint uncertainty representation is supplied:

```text
uncertainty_status = not_supplied
```

## Analysis weights for the first 2010 -> 2024 1% sample smoke

`samplerCensoARG` v2 intentionally leaves generic `analysis_weight` unset and treats inverse selection probabilities as design/audit metadata only.

For the first bounded research smoke, the intended estimation design is explicit unit weighting:

```text
design_id = unit_weight_target_year_sample_research_v1
analysis_weight = 1.0 per sampled household
```

This must not be mislabeled as a sampler-provided weight or official population estimator.

## Monetary compatibility

Predictive welfare and regional CBA/CBT must share the same linear monetary reference before measurement. A positive scalar conversion applied to welfare must be applied identically to point locations and residual values.

The first integration target is `2024-Q3`; basket packaging should therefore select the exact 2024-Q3 regional slice from the governed `canastasINDEC` v2 candidate.

## First acceptance sequence

1. direct observed EPH household welfare -> actual adult-equivalent CBA/CBT -> deterministic FGT0/1/2;
2. P1-R OOF predictive welfare -> the same household-specific lines -> predictive expected FGT0/1/2;
3. compare direct vs predictive FGT on the complete EPH household cohort;
4. if acceptable, apply the frozen predictive welfare release to the exact 469,172-person / 141,863-household target-year Census sample;
5. aggregate unit-weight research FGT estimates, keeping Q8 transport caveats attached.

Collective/private dwelling refinement is explicitly deferred for this first smoke.
