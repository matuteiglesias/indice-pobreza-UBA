# Local commissioning marathon — EPH agglomerates G1→G7

This mission materializes the cloud-implemented agglomerate path on real local data.

## Non-negotiable scope

Do not alter Telescope-A poverty measurement, Census sampling/probabilities/weights,
or model semantics. Do not use spatial overlays for agglomerate membership. Do not infer
an administrative parent. Do not substitute national/ARG for EPH coverage. Do not
calibrate Census-target population mass by agglomerate. Do not manufacture missing parents.

Agglomerate aggregate identity is exactly:

~~~
geography_level = eph_coverage
geography_id    = EPH_TOTAL
~~~

## Repositories / branches

Use clean worktrees if main checkouts are dirty.

- argentina-geography: feat/eph-agglomerate-first-class / PR #42
- samplerCensoARG: feat/eph-agglomerate-g1-parent / PR #18
- indice-pobreza-UBA: feat/eph-agglomerate-g3-g5 / PR #38
- argentina-poverty-atlas: feat/eph-agglomerate-third-level / PR #34

Never merge as part of this mission.

## Phase 1 — G1 exact-source geography

In argentina-geography:

~~~
rm -rf /home/matias/data/aglo-g1-a6 \
       /home/matias/data/aglo-g1-a6-source \
       /home/matias/data/aglo-g1-a7-source \
       /home/matias/data/eph-agglomerates-g1

python -m argentina_geography.sources.indec_2010_radio materialize \
  --source-dir /home/matias/data/aglo-g1-a6-source \
  --output /home/matias/data/aglo-g1-a6

python -m argentina_geography.sources.indec_2010_radio verify \
  --release /home/matias/data/aglo-g1-a6

python -m argentina_geography.derived.indec_eph_agglomerate_exact \
  --census-parent-release /home/matias/data/aglo-g1-a6 \
  --source-dir /home/matias/data/aglo-g1-a7-source \
  --output /home/matias/data/eph-agglomerates-g1

python -m argentina_geography.derived.indec_eph_agglomerate verify \
  --release /home/matias/data/eph-agglomerates-g1
~~~

Hard gates:
- A6 raw snapshot c9184f47fd46c8a47e2c15e5c734b7b6ceb660ce737e18430691f6fbff3c53e8;
- A7 raw snapshot 9b372c33aa6827705e354f9be3545bf80bd668e44acfb602b6b63aabbe2704b8;
- direct radio→agglomerate relation 2fdf263982639b6dc7ebfbeeaec3cecc971801debe8adde6ba48043e48641052;
- 26,417 EPH radios;
- exactly 32 native agglomerate IDs;
- exactly the three known source-missing geometry radios;
- no spatial membership inference;
- cross-province agglomerates remain cross-province.

Historical normalized Parquet byte identity for A6 is NOT an acceptance gate.

## Phase 2 — locate governed real parents

Search manifests, not filenames.

Find:
- research.census-target-year-sample/v2 Census-2010 donor-frame releases;
- population-frame JSONs used by existing real predictive province/department releases;
- predictive-welfare releases used by those same releases;
- exact basket JSON parents used by those releases.

Prefer the exact parents referenced by an already-materialized real province release for the
same period. Produce a table:

~~~
period
sample_release
population_frame
welfare_release
basket_parent
existing_province_release
~~~

If more than one plausible parent exists, stop that period and report identities/hashes.

## Phase 3 — G2 sidecar from G1

For each sample:

~~~
python -m censo_sampler.eph_agglomerate_handoff materialize \
  --sample-release <sample-release> \
  --g1-release /home/matias/data/eph-agglomerates-g1 \
  --output <g2-output>

python -m censo_sampler.eph_agglomerate_handoff verify \
  --release <g2-output>
~~~

Report selected and mapped/outside households/persons, represented IDs, and design person
mass. No selected household may disappear.

## Phase 4 — poverty-region binding

Use all eight governed Telescope-A household artifacts plus
/home/matias/data/eph-agglomerates-g1/agglomerate_inventory.csv.

If the existing binding builder expects household_microscope.csv while the actual
commissioned Telescope-A artifact is households.parquet, adapt only the reader; do not
recreate REGION or basket semantics.

Output:

~~~
/home/matias/data/eph-agglomerate-poverty-region-binding.json
~~~

Hard gates: exact 32-ID G1 inventory; exactly one region per agglomerate across all
quarters; only six governed regions; no administrative inference.

## Phase 5 — G3 observed releases, all eight quarters

For each 2024-Q1 ... 2025-Q4:

~~~
python scripts/build_observed_agglomerate_release.py \
  --period <YYYY-QN> \
  --telescope-a <exact Telescope-A directory> \
  --output <observed-release-directory>
~~~

Each release must verify and contain exactly 396 facts = 32×12 + 12, only
eph_agglomerate plus eph_coverage, EPH_TOTAL and never ARG.

Build an 8-row parity audit against the Telescope-A national person FGT0 poverty and
indigence from the same quarter. Any difference beyond numerical roundoff is a blocker.

## Phase 6 — augment real population frames

For each population frame paired with G2:

~~~
python scripts/augment_population_frame_agglomerate.py \
  --frame <existing population-frame.json> \
  --geography-patch <g2>/population_frame_geography_patch.json \
  --output <augmented-population-frame.json>
~~~

Hard gates: exact household identity; persons unchanged; weights unchanged; outside-frame
households retained with null agglomerate.

## Phase 7 — G5 predictive releases

Start with 2024-Q3 using the exact welfare and basket parents of the commissioned real
predictive province release:

~~~
python scripts/build_predictive_geography_release.py \
  --period 2024-Q3 \
  --geography-level eph_agglomerate \
  --welfare-release <real-quarter-welfare> \
  --frame <augmented-population-frame.json> \
  --baskets <real-quarter-basket-parent> \
  --threshold-area-binding \
    /home/matias/data/eph-agglomerate-poverty-region-binding.json \
  --output /home/matias/data/poverty-aglo-predictive-2024-q3
~~~

Hard gates: 396 facts; exact 32 IDs; eph_coverage/EPH_TOTAL; no ARG; only mapped
households contribute; weights unchanged; no population calibration; no administrative
region_id used to choose agglomerate poverty lines.

If Q3 passes, run every other quarter with exact governed parents. Missing quarter parents
block only that quarter.

## Phase 8 — G7 commissioning

For every period with both releases:

~~~
python science/commissioning/compare_agglomerates.py \
  --observed-release <observed> \
  --predictive-release <predictive> \
  --output <commissioning-period-dir>
~~~

Collect EPH_TOTAL observed/predictive poverty and indigence, delta pp, and the five largest
absolute agglomerate deltas for each concept. Produce one longitudinal tidy CSV.

## Phase 9 — Atlas real-data ingest

Use the Atlas agglomerate branch. Start with the eight observed releases as the reference
surface.

~~~
export AGGLOMERATE_GEOGRAPHY_RELEASE_DIR=/home/matias/data/eph-agglomerates-g1
export POVERTY_RELEASE_DIRS="<colon-separated observed release directories>"

npm run data:project
npm run verify
~~~

Acceptance:
- Aglomerados EPH is a third geography level;
- exactly 32 named geographies;
- aggregate.json carries eph_coverage/EPH_TOTAL;
- no ARG fact in the agglomerate surface;
- URL state accepts level=eph_agglomerate&place=32;
- table/search/aggregate timeline work;
- map remains explicitly blocked until G1 geometry is separately published to Mapbox;
- no fabricated tileset/source-layer claim.

## Final report

Return G1 inventory/QA, G2 coverage, eight-quarter G3 parity, successful G5 periods and
coverage QA, G7 EPH_TOTAL/largest deltas, Atlas verify result, exact blockers, and no merge.
