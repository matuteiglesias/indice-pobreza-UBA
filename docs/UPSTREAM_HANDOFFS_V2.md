# Poverty Estimation v2 — upstream handoff specification

This document tells upstream producers what Poverty needs next. It is intentionally written from the consumer boundary outward so tomorrow's work on `samplerCensoARG` and income-model promotion/inference has a concrete target.

The names below are target contract families, not a demand that sibling repositories immediately rename their current artifacts. During migration, an adapter may prove compatibility between an existing release and the target semantics.

## Handoff A — population/frame

### Producer candidates

- `samplerCensoARG` for reproducible CPV-derived samples/frames;
- an explicit downstream projection/inference surface if a later-period population frame is constructed.

### Required semantic fields

At minimum:

```text
person_id
household_id
sex
age
frame_vintage
sample/inclusion identity
geographic grouping IDs required by the requested release
```

At household/frame level, the release must make explicit:

```text
sampling_design
inclusion_probability or equivalent
weight_semantics
projection_semantics
population_target, if any
```

Optional future fields:

```text
replicate_weight_set / design representation
stratum
cluster
```

### Must not be intrinsic Census-frame semantics

```text
poverty_region
basket_region
poverty_line_region
```

If a six-region poverty-line mapping is required, it should be a separate, versioned threshold-area binding using stable geography IDs. That mapping may be deterministic and simple; it is still not a Census geographic identity.

### Time semantics

A CPV-2010 sample must declare:

```text
frame_vintage = 2010
```

It may additionally declare an analysis or projection target, but must not relabel itself as a 2024/2025 Census merely because it is used for a later poverty estimate.

### Poverty-side stop conditions

Poverty will refuse or defer a real run when:

- household/person identity is not exact;
- household membership is incomplete;
- weight meaning is ambiguous;
- a later-period projection is embedded but undocumented;
- the frame requires poverty to reconstruct geography.

## Handoff B — deployable welfare estimates

### Producer candidates

- promoted model package/evidence from `income-modeling-eph`;
- a separate Census scoring/inference runtime consuming that promoted package and an exact frame.

### Core output

Poverty wants *welfare*, not a model-specific latent transform.

Conceptual minimum:

```text
person_id or household_id
welfare_period
welfare_amount
currency
price_reference
welfare_concept
estimation_status
model/scoring release lineage
```

For the current project, the first likely welfare concept is a released linear ARS income concept compatible with household-total construction. The exact concept must be named rather than assumed from a legacy variable such as `P47T`.

### Transformation boundary

The welfare release must already resolve:

- log/log+1 inversion;
- any bias/retransformation correction;
- clipping/censoring policy;
- monetary normalization;
- model calibration required for deployment;
- missing-prediction policy.

Poverty must not call `10 ** prediction` merely because a research model emitted `log10(P47T)`.

### Uncertainty-ready shape

Preferred future interface for joint predictive uncertainty:

```text
person_id
draw_id
welfare_amount
```

where a `draw_id` represents one coherent joint draw over all units relevant to an estimate. Independent per-person standard errors are not automatically sufficient to reconstruct aggregate poverty uncertainty.

Alternative uncertainty representations are acceptable only with an explicit interpretation and aggregation rule.

### Compatibility requirements

- exact namespace with the population/frame;
- exact welfare/estimation period;
- exact currency and price reference compatible with poverty lines;
- one welfare concept per release or an explicit measure key;
- no extra/missing IDs without an explicit coverage status.

## Handoff C — poverty method

This repository owns this handoff.

Target object:

```text
research.poverty-method/v1
```

It should package:

- method ID/version;
- source/provenance;
- adult-equivalence rules/table;
- threshold comparison semantics;
- household welfare concept;
- person inheritance rule;
- FGT definitions;
- supported demographic domain;
- known deviations/limitations.

P1 creates the first contract.

## Handoff D — poverty lines

### Producer candidates

- `canastasINDEC` only after a reproducible observed-source candidate is proven;
- a future dedicated official-line source adapter if that becomes cleaner.

### Target minimum

```text
threshold_area_id
period
cba_per_adult_equivalent
cbt_per_adult_equivalent
currency
price_reference
methodology_id
source_status
source_release
```

The product must distinguish observed official/source values from derived, imputed or projected values.

### Region binding

If the poverty-line source is regional, another exact input/binding must resolve each household geography to one `threshold_area_id`.

That binding belongs to the line/application layer, not to Census sampling identity.

## Target run identity

A future poverty run should be understandable from explicit parent identities resembling:

```text
population_frame_release
welfare_release
poverty_method_release
poverty_line_release
threshold_area_binding_release (when needed)
```

and explicit clocks:

```text
frame_vintage
welfare_period
poverty_line_period
estimation_period
```

## Tomorrow's producer acceptance checklist

### For `samplerCensoARG`

A good next release should move toward:

- stable person/household IDs unchanged;
- `radio_2010_id`, `department_2010_id`, `province_2010_id` derived from governed geography identity;
- explicit `frame_vintage=2010`;
- sampling/inclusion/weight semantics separated from any projection policy;
- removal or deprecation of poverty-region classification as an intrinsic geography requirement;
- enough design information to state which estimands the weight supports.

### For model promotion / Census inference

A good promoted/deployed release should move toward:

- no poverty-time import of `income-modeling-eph`;
- exact model artifact identity and feature contract;
- scoring over one exact Census/frame release;
- output in an approved linear welfare concept;
- explicit monetary reference;
- exact frame namespace coverage;
- optional coherent predictive draws;
- QA proving no hidden feature substitutions or silent retransformation.

## What Poverty promises in return

If producers satisfy these handoffs, Poverty should not ask them to know about:

- CBA/CBT household threshold calculation;
- adult-equivalence mechanics;
- poverty/indigence classification;
- FGT statistics;
- publication-quality poverty diagnostics;
- poverty-specific maps or output formatting.

The purpose of this boundary is to let upstream repositories stay scientifically focused while making the terminal poverty estimate much easier to defend.
