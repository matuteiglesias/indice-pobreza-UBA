# Stage 04 Geo

## Purpose
Produce map-ready geospatial outputs by joining aggregated poverty indicators to configured geographic layers.

## Inputs
- `stage_02_poverty.household_geo`
- `stage_02_poverty.household_poverty`
- or `stage_03_stats.stats_table` if geo aggregation is based on pre-aggregated tables
- configured geographic shapes

## Output
### geo_layer
- Format: `geojson`
- Filename:
  `poverty_map__base={base}__geo={geo_level}__frac={frac}__tag={experiment_tag}.geojson`

## Primary key
No strict primary key at file level.
Expected uniqueness is one row per geographic unit for the selected view.

## Required columns
- geometry
- geographic id column matching configured `geo_level`
- indicator columns needed for publication

## Invariants
- Output geometry must be valid
- Join cardinality must be checked explicitly
- Stage should not recompute upstream business logic beyond geo aggregation and formatting