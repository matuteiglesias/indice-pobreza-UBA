# Poverty v2 → Argentina Poverty Atlas consumer contract

Status: executable fixture contract, 2026-08-26.

This document defines the artifact seam between `matuteiglesias/indice-pobreza-UBA` and `matuteiglesias/argentina-poverty-atlas`.

The Atlas is a release consumer. It must not import this repository's Python package, re-run poverty measurement, infer geography semantics, or reinterpret weights.

## Producer bundle

A `poverty-estimate-release/v2` directory contains exactly:

```text
poverty_estimates.csv
capabilities.json
geography_join_contract.json
release_manifest.json
run_qa.json
LIMITATIONS.md
checksums.sha256
```

`verify_estimate_release(...)` is the producer-side detached verifier.

## Stable fact key

`poverty_estimates.csv` is keyed by:

```text
release_id
estimation_period
universe
geography_level
geography_id
concept
estimand
```

The current numeric measure is:

```text
estimate
unit = proportion
```

with design/coverage/uncertainty metadata retained on each row.

The Atlas must not aggregate rows into a new scientific estimand unless a future contract explicitly authorizes that operation. National/province/department values intended for publication should be released by Poverty at the corresponding declared geography level.

## Capability discovery

Consumers should drive selectors from `capabilities.json`, not from hard-coded assumptions about what Poverty ought to contain.

The file exposes:

- scientific status;
- available periods;
- available universes;
- available geography levels;
- available concepts;
- available estimands;
- the exact availability cells and geography count for each cell.

Example logical cell:

```text
2024-Q1 × persons × province_2010 × poverty × fgt0
```

A consumer must not offer a selector state absent from `availability`.

## Geography join

`geography_join_contract.json` declares:

```text
join_key = [geography_level, geography_id]
join_semantics = exact_governed_id
geometry_owner = matuteiglesias/argentina-geography
geometry_embedded = false
```

`joinable_geography_levels` is derived from the actual release rows rather than hard-coded to departments.

The Atlas must separately pin a compatible `argentina-geography` Geography Release and prove full/expected ID coverage before rendering a map.

No fuzzy joins, numeric coercion, provider substitution or geometry repair belongs at this boundary.

## Scientific status

Current allowed release statuses are:

```text
synthetic_fixture
research_estimate
```

`synthetic_fixture` values must be presented as demonstration data only and never as estimates.

`research_estimate` remains a research output and must not be presented as an official INDEC publication.

The Atlas should derive disclaimers from release metadata, not from route-specific hard-coded copy.

## Uncertainty

When the release says:

```text
uncertainty_status = not_supplied
```

Atlas may display the point estimate and the limitation, but must not manufacture standard errors, confidence intervals, CVs or uncertainty labels.

Future uncertainty fields should be added through an explicit release-contract evolution.

## Province-first Atlas proof

The Atlas fixture UI is province-first. Poverty's estimator already supports arbitrary declared grouping levels.

The executable producer proof is:

```bash
make atlas-contract-smoke
```

It builds and verifies a synthetic `province_2010` Poverty release without adding any province-specific special case to the release packager.

This proves that a future real province release can enter the Atlas through the same contract.

## Consumer workflow

A robust Atlas ingest should be conceptually:

```text
receive/copy exact Poverty release
        ↓
verify checksums + manifest/schema
        ↓
read scientific_status + capabilities
        ↓
select an available measure cell
        ↓
validate geography_level against join contract
        ↓
pin compatible Argentina Geography release
        ↓
prove geography_id coverage
        ↓
project static browser facts
        ↓
render / chart / map
```

The browser should consume a bounded static projection of already-verified facts. Scientific verification should happen during Atlas build/ingest, not be delegated to UI components.

## Things deliberately not shared as code

There is no Python import from Poverty into Atlas and no JavaScript package exported from Poverty merely for one consumer.

The stable seam is the release bundle. If a schema primitive becomes useful across several research products, assess it for `empirical-data-contracts` rather than creating a Poverty-specific SDK.
