# Poverty Estimation v2 — P3/P4/release handoff

Status date: 2026-08-26.

This handoff records the concrete interfaces now available for tomorrow's `samplerCensoARG` and income-model promotion/Census-inference work, plus the downstream boundary for a future map/web consumer.

## Completed work

### P3 — upstream semantic contracts

Merge SHA:

```text
5ae9613d54c2420fab966d1bb546c504d2ff9c6a
```

Poverty now has explicit in-memory contracts for:

```text
PopulationFrameRelease
WelfareRelease
PovertyLineRelease
ThresholdAreaBindingRelease
```

The frame carries stable Census IDs, frame vintage, sampling-design identity, frame-selection probability and analysis weight. It does **not** carry an intrinsic poverty/basket region.

The welfare release is household-level, already linear, content-compatible with the frame namespace and explicit about period/currency/price reference/welfare concept.

The poverty-line release pins the exact poverty method:

```text
argentina.indec-line-poverty-2016@v1
```

A separate threshold-area binding resolves:

```text
department_2010_id -> threshold_area_id
```

using IDs only. No spatial operation occurs in Poverty.

`prepare_measurement_inputs(...)` turns compatible producer-shaped objects into the exact P2 scientific inputs:

```text
PersonMember
HouseholdWelfare
HouseholdPovertyLines
```

## P4 — generic weighted estimation

Merge SHA:

```text
8f74576b638683d33a88a8ac64bf4c5fa9e6e8c8
```

The new estimator consumes:

```text
PovertyMeasurement
HouseholdDomain
EstimationDesign / HouseholdWeight
EstimationContext
```

and emits weighted:

```text
poverty.fgt0 / fgt1 / fgt2
indigence.fgt0 / fgt1 / fgt2
```

for both household and person universes.

The estimator is not hard-coded to departments. `department_2010` is the first acceptance application, while arbitrary declared grouping levels are supported as domain keys.

National rows reconcile to domain numerators/denominators.

The current design deliberately does not emit population/poor counts merely from a generic analysis weight. Totals require an explicit design contract identifying the population target.

When no justified uncertainty representation exists:

```text
uncertainty_status = not_supplied
```

No standard errors or intervals are fabricated.

## V2 estimate release

Merge SHA:

```text
f831d07756cf74712050ad6abab8f7df5b28d394
```

A deterministic synthetic end-to-end path now proves:

```text
producer-shaped P3 fixtures
        ↓
P2 measurement
        ↓
P4 estimation
        ↓
poverty-estimate-release/v2
```

The bundle is:

```text
poverty_estimates.csv
release_manifest.json
run_qa.json
LIMITATIONS.md
checksums.sha256
geography_join_contract.json
```

It is checksum-verified, deterministic across reruns and tamper-detecting.

## Exact seam for sampler tomorrow

A useful `samplerCensoARG` successor/adapter should make it straightforward to populate:

```text
PopulationFramePerson
  person_id
  household_id
  sex
  age
  radio_2010_id
  department_2010_id
  province_2010_id

PopulationFrameHousehold
  household_id
  department_2010_id
  province_2010_id
  frame_selection_probability
  analysis_weight

PopulationFrameRelease
  release_id
  namespace
  frame_vintage
  sampling_design_id
  weight_semantics
```

The frame should not need `poverty_region`, `basket_region` or `poverty_line_region` as intrinsic Census geography.

## Exact seam for model promotion / Census inference tomorrow

The most direct first producer target is household welfare:

```text
WelfareRelease
  release_id
  frame_namespace
  welfare_period
  currency
  price_reference
  welfare_concept = household_total_family_income

WelfareEstimate
  household_id
  welfare_amount
  estimation_status
```

`welfare_amount` must already be in approved linear monetary units. Poverty must not import the research model, invert logs, apply smearing, calibrate, clip or guess missing predictions.

If the promoted model naturally scores persons, the scoring/inference layer must own the explicit construction of the approved household welfare concept before this handoff, or publish a separately approved intermediate contract rather than making Poverty infer it implicitly.

## Exact seam for poverty lines

Poverty expects a release containing:

```text
period
currency
price_reference
method_release_id
threshold_area_id
cba_per_adult_equivalent
cbt_per_adult_equivalent
```

plus a separate exact geography-ID binding where regional lines require one.

The current synthetic source stands in for a future governed `canastasINDEC`/official-line release.

## Exact seam for map/web consumption

A map utility does not need the Poverty internals above. It consumes the verified release and filters a measure, for example:

```text
universe = persons
concept = poverty
estimand = fgt0
geography_level = department_2010
```

The resulting fact rows contain:

```text
geography_id
estimate
```

and `geography_join_contract.json` declares:

```text
join_key = [geography_level, geography_id]
geometry_owner = matuteiglesias/argentina-geography
geometry_embedded = false
join_semantics = exact_governed_id
```

A future mapper should pin a compatible Geography Release, join exact IDs and own geometry/rendering itself. Poverty should not regain GeoJSON, shapefile, projection or tile responsibilities.

## Current focused checks

```bash
make method-check
make measurement-check
make v2-contracts-check
make estimation-check
make v2-release-smoke
```

The legacy v1 `make poverty-release-smoke` remains green as regression compatibility.

## Next scientifically useful waves

Do not add more synthetic plumbing by default. The next high-value work should be one of:

1. replace the synthetic population-frame parent with an exact sampler release/adapter;
2. replace synthetic welfare with an exact promoted-model Census-inference release;
3. replace synthetic lines with a governed real poverty-line release;
4. P5 uncertainty propagation once coherent draws/replicates are actually available;
5. a thin external map/web consumer proving the exact geography join.

A real Poverty release should only begin when the exact producer parents exist and their semantics satisfy these already-tested boundaries.
