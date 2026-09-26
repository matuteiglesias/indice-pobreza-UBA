# G2 — EPH agglomerate handoff at the Poverty boundary

This seam adds no estimand, model, sampling rule or poverty computation.

## Population-frame augmentation

`scripts/augment_population_frame_agglomerate.py` consumes:

- the existing population-frame JSON already used by the predictive geography producer;
- `population_frame_geography_patch.json` from samplerCensoARG's A7 sidecar.

It requires exact household identity and only appends:

```text
eph_agglomerate_id       nullable
mapped_to_eph_frame      boolean
```

Household order, person payload, analysis weights and every pre-existing field
are preserved. Radios outside the official EPH frame remain in the population
frame with a null agglomerate ID.

## Poverty-region binding

Poverty-region semantics remain owned downstream of argentina-geography.

`scripts/build_eph_agglomerate_region_binding.py` consumes governed
Telescope-A `household_microscope.csv` outputs plus the G1
`agglomerate_inventory.csv`.

Telescope A has already converted native EPH `REGION` to the six canonical
`basket_region` values. The binding builder therefore only verifies that every
native agglomerate has one and only one basket region across supplied periods:

```text
eph_agglomerate_id -> poverty_region_id
```

The A7/G1 ID inventory must match exactly. Conflicts or missing IDs fail closed.

## Explicit non-changes

- zero new poverty estimands;
- zero new poverty classifications;
- zero model changes;
- zero sampling changes;
- zero weight changes;
- zero GIS inference;
- zero duplication of REGION-to-basket semantics.

The result is a geography/policy handoff ready for a later
`geography_level=eph_agglomerate` release producer.
