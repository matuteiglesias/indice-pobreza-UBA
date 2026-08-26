# P2 — pure FGT poverty measurement kernel

## Purpose

`poverty_pipeline.science.measurement` is the new smallest scientific unit of the repository.

It answers one question only:

> given household members, already-resolved linear household welfare, household-specific CBA/CBT values per adult equivalent, and one versioned poverty method, what are the household poverty/indigence status and FGT contributions, and what status/contribution does each person inherit?

It deliberately stops **before** population estimation.

## Inputs

### `PersonMember`

```text
person_id
household_id
sex
age
```

Sex is already mapped to the method's canonical domain. P2 does not know source codes such as EPH/Census `1`/`2`.

### `HouseholdWelfare`

```text
household_id
amount
```

`amount` must already be a nonnegative, finite, linear monetary household welfare concept. P2 never exponentiates model output, calibrates a model or sums a model-specific latent quantity.

### `HouseholdPovertyLines`

```text
household_id
cba_per_adult_equivalent
cbt_per_adult_equivalent
```

The applicable threshold area/period has already been resolved outside the kernel. P2 does not know regions or geography.

### `PovertyMethod`

P2 consumes the P1 object `argentina.indec-line-poverty-2016@v1` or a future compatible method version.

## Household calculation

For household `h`:

```text
AE_h  = sum(adult_equivalent(person))
CBA_h = cba_per_AE_h * AE_h
CBT_h = cbt_per_AE_h * AE_h
```

Under method v1:

```text
indigent_h = welfare_h <= CBA_h
poor_h     = welfare_h <= CBT_h
```

CBA must not exceed CBT.

## FGT contribution

For line `z > 0`, welfare `y >= 0` and `alpha` in `{0,1,2}`:

```text
shortfall = max((z - y) / z, 0)

FGT0 = 1 if under the method line, else 0
FGT1 = shortfall if under the line, else 0
FGT2 = shortfall**2 if under the line, else 0
```

At exact equality under method v1:

```text
FGT0 = 1
FGT1 = 0
FGT2 = 0
```

This preserves the explicit inclusive classification rule while maintaining zero normalized depth at the line.

The kernel also reports positive monetary shortfall:

```text
max(line - welfare, 0)
```

rather than retaining the legacy configurable gap-sign convention.

## Person contribution

People inherit the household's classification, matching the poverty-method rule.

P2 also exposes inherited household FGT contributions on each person record. The field names deliberately begin with `inherited_` for FGT quantities beyond status: they are **not** computed from an individual welfare concept or an individual line.

This supports a later person-universe estimator while preserving the scientific interpretation.

## What P2 does not do

The module has no responsibility for:

- sampling or projection weights;
- aggregation by department/region/nation;
- standard errors or confidence intervals;
- welfare draws;
- geography;
- CBA/CBT source acquisition;
- monetary conversion;
- income-model inference or retransformation;
- release manifests or packaging;
- maps/plots.

These omissions are intentional. They are what make the kernel independently testable.

## Important compatibility point

The existing `household_poverty.py` remains available for the v1 release path. P2 does not silently redirect existing releases to the new FGT kernel.

A later migration can compare v1 and P2 classifications on exact fixtures before retiring old policy knobs.

## Analytic regression examples

Tests include the household composition used by INDEC's methodology examples:

```text
woman age 35   0.77
man age 18     1.02
woman age 61   0.67
------------------
total           2.46 adult equivalents
```

and the five-person example totaling `3.25` adult equivalents.

The tests also prove:

- zero welfare -> FGT0=FGT1=FGT2=1;
- equality -> classified under the line with zero depth;
- welfare above CBT -> zero poverty contributions;
- person inheritance;
- fail-closed behavior for bad IDs, orphan members, incomplete line coverage, invalid demographics, non-finite values and CBA > CBT.

## Next seam

P3 should adapt future producer releases into these four in-memory concepts without teaching this module anything about Census, EPH or model internals.
