# Poverty Estimate Release v2

`poverty-estimate-release/v2` is the first target public/scientific artifact of the v2 architecture. It is intentionally a **fact-table release**, not a map.

## Files

```text
poverty_estimates.csv
release_manifest.json
run_qa.json
LIMITATIONS.md
checksums.sha256
geography_join_contract.json
```

The release contains no geometry.

## Estimate grain

One row is uniquely identified by:

```text
release_id
estimation_period
universe
geography_level
geography_id
concept
estimand
```

Current universes:

```text
households
persons
```

Current concepts:

```text
poverty
indigence
```

Current estimands:

```text
fgt0
fgt1
fgt2
```

`fgt0` is incidence/headcount proportion; `fgt1` is normalized gap; `fgt2` is severity. The latter two are project analytical extensions rather than claims about standard INDEC headline publication.

## Geography boundary

`geography_level` + `geography_id` are foreign keys only. Poverty does not own the polygon represented by the ID and does not load geometry to produce the estimate.

The initial synthetic/acceptance application uses:

```text
geography_level = department_2010
geography_id    = stable department_2010_id
```

A mapping or web consumer should:

1. verify this Poverty release;
2. choose a measure, typically `universe=persons`, `concept=poverty`, `estimand=fgt0`;
3. retain rows with `geography_level=department_2010`;
4. resolve those exact IDs against a pinned compatible Geography Release from `matuteiglesias/argentina-geography`;
5. join by exact governed ID;
6. own rendering, projections, tiles, legends and web interaction itself.

The `national` rows are explicitly non-spatial.

## Example consumer query

Conceptually:

```text
poverty_estimates
  WHERE universe = persons
    AND concept = poverty
    AND estimand = fgt0
    AND geography_level = department_2010
```

yields a map-ready table resembling:

```text
geography_id   estimate
02001          ...
06014          ...
```

No spatial operation is needed until a consumer chooses to render it.

## Exact parents

Every release retains content-identified parent refs for the population frame, welfare estimates, poverty lines, threshold-area binding and poverty method. A real release must replace fixture identities with exact producer release IDs/hashes.

## Uncertainty

The first point-estimate release writes:

```text
uncertainty_status = not_supplied
```

This is an explicit scientific result: point estimates exist but uncertainty has not been supplied by a justified upstream representation. Standard errors, confidence intervals and CVs are not fabricated.

P5 may extend the release schema only after coherent welfare draws, replicate weights or another approved uncertainty representation exists.

## Population totals

The current estimator deliberately emits FGT proportions only. It does not infer current population totals merely because an `analysis_weight` exists. Counts/totals require an estimation design that explicitly identifies the corresponding population target.

## Fixture status

`make v2-release-smoke` builds a deterministic synthetic release exercising:

```text
P3 producer contracts
  -> P2 measurement
  -> P4 weighted estimation
  -> v2 release packaging
```

The fixture is not an estimate of Argentine poverty and must never be presented as official statistics.
