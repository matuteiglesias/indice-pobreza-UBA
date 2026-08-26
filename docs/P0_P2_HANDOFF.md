# Poverty Estimation v2 — P0/P1/P2 handoff

Status date: 2026-08-26.

This handoff records the concrete boundary now available for the next work on Census sampling and income-model promotion/inference.

## Completed waves

### P0 — architecture reset

Merge SHA: `b71182b2958974afa233197c1a776884b38376ee`

Established:

- Poverty is the terminal scientific authority for poverty measurement/estimation, not an EPH/Census/model/GIS workspace.
- direct logical inputs are population/frame, welfare estimates, poverty method and poverty lines;
- `frame_vintage`, `welfare_period`, `poverty_line_period` and `estimation_period` are distinct concepts;
- poverty-line region is not intrinsic Census geography;
- uncertainty may be propagated when supplied, never manufactured;
- exact upstream handoff expectations live in `docs/UPSTREAM_HANDOFFS_V2.md`.

### P1 — versioned poverty method

Merge SHA: `8055cf58e8c6b33aec83332a7e2c0c313701c72f`

Method release identity:

```text
argentina.indec-line-poverty-2016@v1
```

Machine-readable method:

```text
configs/poverty_methods/indec-line-poverty-2016-v1.json
```

Code API:

```python
from poverty_pipeline.science import load_poverty_method

method = load_poverty_method(
    "configs/poverty_methods/indec-line-poverty-2016-v1.json"
)
```

Frozen semantics include:

- household total-family-income welfare concept;
- CBA/CBT household thresholds from adult equivalents;
- inclusive `income <= line` classification in method v1;
- persons inherit household status;
- current operational adult-equivalence age/sex table;
- exact `61–75` / `76+` terminal boundary;
- FGT0/1/2 definitions as project analytical extensions.

The old v1 candidate adult-equivalence fixture remains regression evidence and is not silently rewritten.

### P2 — pure FGT measurement kernel

Merge SHA: `72ffe50c0a8666852fdeef6aa0929e315dada814`

Code API:

```python
from poverty_pipeline.science import (
    PersonMember,
    HouseholdWelfare,
    HouseholdPovertyLines,
    measure_poverty,
)
```

The kernel accepts:

```text
PersonMember
  person_id
  household_id
  canonical sex
  completed age

HouseholdWelfare
  household_id
  already-linear nonnegative welfare amount

HouseholdPovertyLines
  household_id
  CBA per adult equivalent
  CBT per adult equivalent

PovertyMethod
```

It produces household:

```text
adult_equivalents
household_cba
household_cbt
poor / indigent
poverty FGT0 / FGT1 / FGT2
indigence FGT0 / FGT1 / FGT2
positive monetary shortfalls
```

and person records with explicitly **inherited** household status/FGT contributions.

It does not know about:

- weights;
- sampling design;
- uncertainty draws;
- Census/EPH source codes;
- regions/geography;
- model transforms;
- files/manifests;
- plots/publication.

## Tomorrow: exact producer seams

### `samplerCensoARG`

The most useful evolution is a frame release that can be adapted to `PersonMember` plus later estimation-design inputs without Poverty-specific geography hacks.

Desired direction:

```text
stable person_id / household_id
sex / age
radio_2010_id
department_2010_id
province_2010_id
frame_vintage = 2010
sampling/inclusion semantics
weight semantics
optional replicate/design information
```

Do not make `poverty_region` / `basket_region` an intrinsic Census geography field in the next contract. If threshold-region mapping is needed, publish/bind it separately using governed geography IDs.

### income model promotion / Census inference

The most useful output is **not** a log prediction that Poverty exponentiates.

Desired direction:

```text
exact Census/frame namespace
household_id (or exact person IDs plus an explicit upstream household-welfare construction)
welfare_period
approved linear welfare amount
currency
price_reference
welfare_concept
model/scoring release lineage
coverage/status
optional coherent draw_id representation
```

The scoring/deployment layer must own:

- log inversion/retransformation;
- calibration;
- clipping/censoring decisions;
- missing-prediction handling;
- exact feature contract;
- model artifact loading.

Poverty should receive the finished welfare concept.

## Still intentionally unresolved

P0-P2 do **not** yet decide:

- the final v2 serialized population-frame artifact name/schema;
- the final welfare-estimate artifact name/schema;
- the real poverty-line producer/release;
- sampling-weight estimands beyond the existing v1 behavior;
- uncertainty representation and interval method;
- official EPH parity tolerances;
- the first real small-area release period.

These are P3+ responsibilities and should be resolved with exact producer evidence, not guessed in advance.

## Acceptance pressure for upstream work

A good upstream change tomorrow should make it easier to construct these three P2 inputs:

```text
PersonMember
HouseholdWelfare
HouseholdPovertyLines
```

without adding any new knowledge of upstream implementation to the measurement kernel.

If an upstream change instead requires Poverty to import a model repo, understand shapefiles, infer a Census period, or guess a monetary transform, the boundary is moving in the wrong direction.

## Verification

Focused checks:

```bash
make method-check
make measurement-check
```

The full existing synthetic v1 release smoke remains green and is intentionally preserved as regression compatibility while the v2 path evolves.
