# Poverty consumer-lineage audit and proposed Batch 2 slice

**Audit date:** 2026-08-04<br>
**Scope:** downstream-consumer characterization only<br>
**Status:** evidence-based specification; no scientific execution or validation

## 1. Decision summary

This repository is not presently a reproducible end-to-end poverty system. It is a
notebook workspace whose nominal path is Census sampling/adaptation → four-stage
income prediction → household poverty classification → descriptive aggregation →
geographic export. The checked-in structural smoke test passes, but the nominal
path depends on an absent Census database, sibling repositories, absolute paths,
unpinned raw-GitHub files, serialized legacy models, and mutable “today” prices.
Consequently **none of notebooks 1–5 is independently reproducible from this
checkout**.

The poverty-specific seam is narrow and worth preserving:

1. join a person-level income release to a declared Census sample;
2. convert model income from `log10(ARS + 1)` to ARS exactly once;
3. assign adult-equivalent coefficients and regional CBA/CBT values;
4. sum income and thresholds to household-quarter level;
5. classify poverty/indigence and calculate signed gaps; and
6. aggregate a declared universe with an explicit sample/weight policy.

Annual EPH preparation, rank features, employment adjustment, and the four model
stages are upstream income-model concerns. Census sampling and geography are also
producer concerns. Batch 2 should therefore consume versioned releases rather
than repair the sibling-path workflow here.

## 2. Evidence, inspection boundary, and limitations

### Inspected

- repository declarations and documentation: `README.md`, `SYSTEM.yaml`,
  `docs/data.md`, `docs/maintenance.md`, `.gitignore`, and `Makefile`;
- structure check: `scripts/smoke_repo.sh`;
- current ordered notebooks 1–5, `notebooks/funciones.py`, and
  `notebooks/variables.py`;
- supporting notebooks 1 and 6–11 for employment, plotting, cloud/Mapbox upload,
  administration, and historical workflow evidence;
- `notebooks_legacy/` for `EPHARG_train*`, `fitted_RF`, and old rank assumptions;
- tracked `data/info`, geography/electoral reference files, recipes, and existing
  `data/results` file names (presence only, not scientific verification).

### Not available in this checkout

- `income-modeling-eph`, `encuestador-de-hogares`, `samplerCensoARG`,
  `CNE-INDEC-georef`, `geoespacial-censo-IGN`, and the local CPV 2010 database;
- `/media/matias/Elements/suite/{poblaciones,out}` and `/home/matias/repos/...`;
- a lockfile/environment declaration, model manifest, data checksums, release
  manifests, credentials, and a canonical execution command;
- ignored `data/Pobreza`, `data/yr_samples`, `data/training`, `data/Fitted_RF`, and
  `data/geojson` artifacts.

Producer ownership stated below follows `SYSTEM.yaml` and the work-packet
coordination decision; producer contracts and schemas could not be independently
verified. Raw-GitHub availability was deliberately not used as proof of a stable
contract. No network fetch, sibling-repository mutation, full notebook run, model
training, data refresh, deployment, or publication was performed.

## 3. Actual execution graph

Paths in notebook code are relative to the **notebook working directory**, not the
repository root. The notebooks share in-memory variables only conceptually; each
redeclares parameters, sometimes inconsistently.

| Stage | Reads | Transformation / controls | Writes | Executability and hazards |
|---|---|---|---|---|
| 1. Configuration and auxiliary data | `data/info/radio_ref.csv`; mutable `Aglomerados-EPH-INDEC/.../radios_aglo_EPH.csv`; absolute `DPTO_PROV_Region.csv`; sibling `encuestador-de-hogares/data/info/{AGLO_rk,Reg_rk}`; sibling Census sample; absolute CPV database | `FRAC=0.02`, years `[2024,2025)`, `ARG`; `transform_censo_data`; ID generation; optional clone and sampler subprocess | absolute `/media/matias/Elements/suite/poblaciones/table_f0.02_2024_ARG.csv` | Broken here. Networked clone, expensive sampler, directory changes, unpinned inputs, and locally synthesized IDs. |
| 2. Main processing | adapted Census table; local employment series and Census unemployment baseline; sibling `modelos/clf1..clf4`; feature lists in `variables.py` | same fraction/year; employment resampling; four chained predictions via `run_predict_save` | absolute `/media/matias/Elements/suite/out/RFC{1..4}_0.02_<Q>_ARG.csv` | Broken here. Models and inputs absent; serialized-model/sklearn compatibility unknown; missing files are silently skipped. This entire stage duplicates upstream income modeling. |
| 3. Poverty calculation | adapted Census table; `RFC4`; local adult-equivalence, radio and department-region tables; mutable regional basket URL; mutable electoral URL; sibling electoral crosswalk | `FRAC=0.02`, 2024; `P0910`; log-to-linear income; adult-equivalent and basket joins; household sums and comparisons | ignored `data/Pobreza/{geo_households,individual_income,household_poverty}_...csv` | Broken here. Poverty core is usable only after contracts are supplied. Inner/default merges can silently drop rows. Electoral enrichment is not required for poverty. Geography output is overwritten. |
| 4. Descriptive statistics | all three stage-3 families; mutable monthly IPC URL | `FRAC=0.02`, years `[2023,2025)`; converts `P47T_persona` from log again, multiplies monetary columns by current-month/2016-01 IPC; universes P, PAGLO, M24, H, Hp, Hi; many groupers | `data/results/stats_<base>_<groupers>_sample0.02.csv` | Historically runnable only with ignored inputs and network. Repeated append/latest logic can duplicate rows. “Today” makes output non-reproducible. There is a likely double conversion: stage 3 already exponentiates person income, then stage 4 exponentiates it again. |
| 5. Geospatial handling | stage-3 outputs; current IPC; sibling IGN/Census shapefiles (some alternatives are tracked locally) | **`FRAC=0.05`**, inconsistent with stages 1–4; joins aggregates to PROV/DPTO/IDFRAC geometries | `data/geojson/poverty_<base>_<level>.geojson` | Broken/incompatible by default due to fraction mismatch and missing inputs. Potentially expensive geospatial operations. Publication is out of scope. |
| 6/10 publication | GeoJSON, recipes, Mapbox style config | shell calls to delete/upload/create/publish tilesets; embedded tokens | remote Mapbox sources, tilesets, styles | Destructive/networked deployment, not part of poverty computation and must never be implicit. Exposed tokens must be revoked outside this audit. |
| 7/8 plots, 9 administration, 11 nowcasting | result CSVs and assorted external series | exploratory plots, inventories, uploads, experimental projections | figures/HTML/cloud objects | Historical/exploratory. Notebook 9 contains a deliberate `xx` failure and GCS upload commands. Not a production path. |

### Hidden manual steps

1. Start Jupyter with `notebooks/` as the working directory and a compatible,
   undocumented Python/geospatial/scikit-learn environment.
2. Mount the author’s external disk and arrange multiple sibling repositories at
   exact relative paths.
3. Supply a private/local CPV 2010 database and generate a Census sample.
4. Supply legacy rank tables and serialized classifiers with compatible library
   versions.
5. Manually align fractions and year ranges between notebooks.
6. Ensure mutable URLs contain every requested quarter and the current month.
7. Decide whether income is logged or linear before stage 4.
8. Supply cloud/Mapbox CLIs and credentials for optional publication.

## 4. Machine-readable consumer dependency registry

This YAML block is the registry for this one-file packet. Artifact IDs marked
`provisional` are proposed seams, **not existing releases**.

```yaml
registry_version: 1
dependencies:
  - id: annual_eph_preprocessed
    consumer_stage: legacy model training only; must not be consumed by Batch 2 poverty core
    current_reference: notebooks_legacy/**/EPHARG_train_<YY>.csv
    proposed_artifact: artifact:research.eph-annual-input@1  # provisional
    producer: repo.income-modeling-eph
    vintage: exact annual vintage recorded in producer manifest
    files: [annual person-household table, schema.json, manifest.json, checksums]
    schema_keys: [CODUSU, NRO_HOGAR, COMPONENTE, ANO4, TRIMESTRE]
    entity_unit_frequency: person; EPH survey units; annual bundle with quarter
    freshness: immutable release; no latest alias
    mandatory: false for poverty slice; true only for retraining
    availability: unavailable; legacy name observed only
    verification: not verified against producer
    fallback: none; do not train here
    unresolved: exact current columns and mapping from EPHARG_train

  - id: income_predictions
    consumer_stage: poverty calculation
    current_reference: /media/matias/Elements/suite/out/RFC4_<FRAC>_<Q>_ARG.csv
    proposed_artifact: artifact:research.eph-model-output@1  # provisional concrete release required
    producer: repo.income-modeling-eph
    vintage: same target quarter and Census-sample release as slice
    files: [person_income.parquet, manifest.json, schema.json, qa.json, checksums]
    schema_keys: [sample_person_id]
    schema_required: [sample_person_id, sample_household_id, period, income_value, income_unit, income_transform, observed_derived_projected, model_release_id]
    entity_unit_frequency: person; declared ARS reference or log10(ARS+1); quarterly
    freshness: immutable release pinned by digest
    mandatory: true
    availability: unavailable; only ignored/absolute RFC4 path is referenced
    verification: not verified
    fallback: bounded baseline may be approved; never silently use RFC4
    unresolved: model adequacy, transform, monetary reference, training vintage, prediction-domain coverage

  - id: census_sample
    consumer_stage: income join and household/geography keys
    current_reference: samplerCensoARG/data/censo_samples/table_f<FRAC>_<YEAR>_ARG.csv then /media/.../poblaciones
    proposed_artifact: artifact:research.census2010-sample@1  # provisional; generic sampler producer
    producer: repo.sampler-censo-arg (or designated generic Census sampler)
    vintage: CPV 2010 source plus immutable sampling seed/config release
    files: [persons.parquet, households.parquet, manifest.json, schema.json, checksums]
    schema_keys: [sample_person_id, sample_household_id, RADIO_REF_ID]
    schema_required: [sample_person_id, sample_household_id, RADIO_REF_ID, DPTO, PROV, P02, P03, P09, P10, sample_weight]
    entity_unit_frequency: person and household; count/category; fixed 2010 frame projected only if declared
    freshness: immutable, seed-reproducible
    mandatory: true
    availability: absent and gitignored
    verification: not verified
    fallback: none; do not invoke sampler from consumer
    unresolved: legal access, sampler authority, projection meaning, ID stability, weight policy

  - id: adult_equivalence
    consumer_stage: poverty calculation
    current_reference: data/info/adulto_eq.csv
    proposed_artifact: artifact:research.poverty-adult-equivalence@1
    producer: this repository after methodological approval
    vintage: declared INDEC table/version
    files: [adult_equivalence.csv, manifest.json]
    schema_keys: [P02, P03]
    schema_required: [P02, P03, CB_EQUIV]
    entity_unit_frequency: demographic cell; adult-equivalent coefficient; methodology-versioned
    freshness: immutable methodology release
    mandatory: true
    availability: tracked
    verification: presence/schema not scientific provenance
    fallback: none
    unresolved: age intervals, sex coding, provenance and approved version

  - id: regional_baskets
    consumer_stage: poverty calculation
    current_reference: https://raw.githubusercontent.com/matuteiglesias/canastasINDEC/main/data/CB_Reg_defl_Q.csv
    proposed_artifact: artifact:publicdata.regional-baskets-derived@1
    producer: repo.canastasindec
    vintage: exact release covering selected quarter
    files: [regional_baskets_quarterly.csv, manifest.json, methodology.md, checksums]
    schema_keys: [period, region]
    schema_required: [period, region, CBA_per_adult_equivalent, CBT_per_adult_equivalent, currency, price_reference]
    entity_unit_frequency: region-period; ARS per adult equivalent; quarterly
    freshness: immutable and pinned; selected period must have complete regional coverage
    mandatory: true
    availability: mutable URL referenced; older local variants tracked
    verification: not release-verified
    fallback: none; local similarly named files are not interchangeable
    unresolved: deflation method, region spelling, period semantics, monetary base

  - id: ipc_reference
    consumer_stage: aggregation only if output price reference differs from income/basket reference
    current_reference: https://raw.githubusercontent.com/matuteiglesias/IPC-Argentina/main/data/info/indice_precios_M.csv
    proposed_artifact: artifact:publicdata.argentina-ipc@1  # provisional
    producer: repo.ipc-argentina
    vintage: pinned release with source series and base
    files: [ipc_monthly.csv, manifest.json, checksums]
    schema_keys: [month]
    schema_required: [month, index, base_period, source]
    entity_unit_frequency: national month; index; monthly
    freshness: pinned to declared output reference month, never wall-clock today
    mandatory: false when income and baskets already share output reference
    availability: mutable URL plus local historical files
    verification: not release-verified
    fallback: emit native-reference monetary values; do not silently reflate
    unresolved: whether national IPC is methodologically valid for regional baskets

  - id: census_geography_reference
    consumer_stage: attach stable geography keys
    current_reference: data/info/radio_ref.csv and data/info/DPTO_PROV_Region.csv
    proposed_artifact: artifact:publicdata.census2010-geography-reference@1  # provisional
    producer: designated Census/IGN geography producer
    vintage: 2010 geography
    files: [radio_reference.parquet, department_region.csv, manifest.json, checksums]
    schema_keys: [RADIO_REF_ID]
    schema_required: [RADIO_REF_ID, COD_2010, FRAC_REF_ID, DPTO, PROV, region]
    entity_unit_frequency: Census geography; codes; static vintage
    freshness: immutable
    mandatory: true
    availability: tracked candidate tables, provenance/checksums absent
    verification: file presence only
    fallback: none
    unresolved: unique-key guarantees, code padding/types, authoritative region mapping

  - id: eph_agglomerate_mapping
    consumer_stage: optional agglomerate reporting; currently stage 1
    current_reference: mutable radios_aglo_EPH.csv raw URL
    proposed_artifact: artifact:research.eph-census-aligner@1
    producer: repo.eph-censo-aligner
    vintage: release compatible with 2010 geography and selected EPH period
    files: [radio_agglomerate_crosswalk.csv, manifest.json, checksums]
    schema_keys: [COD_2010]
    schema_required: [COD_2010, AGLOMERADO, mapping_status, release_id]
    entity_unit_frequency: Census radio; code; versioned mapping
    freshness: immutable
    mandatory: false for department-only slice
    availability: mutable URL only
    verification: not verified
    fallback: omit agglomerate outputs
    unresolved: XX-to-99 rewrite and unmatched-radio policy

  - id: geometry_department
    consumer_stage: optional GeoJSON
    current_reference: sibling geoespacial-censo-IGN paths; tracked data/geo alternatives
    proposed_artifact: artifact:publicdata.argentina-departments-2010@1  # provisional
    producer: designated geography producer
    vintage: 2010 department boundaries
    files: [departments.gpkg, manifest.json, checksums]
    schema_keys: [DPTO]
    schema_required: [DPTO, PROV, geometry, crs]
    entity_unit_frequency: department; geometry; static
    freshness: immutable
    mandatory: false
    availability: candidate shapefiles tracked, authority not verified
    verification: not spatially verified
    fallback: output non-spatial department table only
    unresolved: CRS, validity, Misiones patch, join coverage, licensing

  - id: employment_series
    consumer_stage: legacy model prediction only
    current_reference: data/info/45.2_ECTDT.csv (referenced but absent); notebook 1 employment download
    proposed_artifact: part of artifact:research.eph-model-output@1 provenance
    producer: repo.income-modeling-eph
    vintage: model-release-defined
    files: [recorded in model manifest]
    schema_keys: [period]
    schema_required: [period, unemployment_rate, source_vintage]
    entity_unit_frequency: national/agglomerate; percent; quarterly
    freshness: pinned to model release
    mandatory: false for poverty consumer
    availability: referenced canonical filename absent; similarly named local files exist
    verification: broken current reference
    fallback: none in this repository
    unresolved: series identity and validity of Census-2010 ratio adjustment

  - id: electoral_crosswalk
    consumer_stage: optional electoral enrichment only
    current_reference: mutable claves_dptos URL plus sibling CNE-INDEC-georef CSV
    proposed_artifact: artifact:publicdata.electoral-census-crosswalk@1  # provisional
    producer: designated electoral crosswalk producer
    vintage: election/geography-specific release
    files: [radio_electoral_crosswalk.csv, department_keys.csv, manifest.json]
    schema_keys: [COD_2010]
    schema_required: [COD_2010, distrito_id, seccion_id, circuito]
    entity_unit_frequency: Census radio; electoral codes; release-specific
    freshness: immutable
    mandatory: false
    availability: tracked copies exist, current notebook uses sibling/URL instead
    verification: not verified
    fallback: omit all electoral columns
    unresolved: ownership, coverage and need; not part of proposed slice
```

## 5. Legacy-name compatibility

No current `EPHARG_annual_input_*` occurrence was found in this repository. That
absence means compatibility cannot be inferred; it is an explicit migration seam.

| Legacy assumption | Current/proposed contract | Classification | Required action |
|---|---|---|---|
| `EPHARG_train_<YY>.csv` in legacy training/stochastic notebooks | versioned `artifact:research.eph-annual-input@1` | **requires migration** | Producer supplies manifest and deterministic column/name adapter; training remains upstream. |
| `EPHARG_annual_input_*` | same annual-input artifact | **unresolved** | No consumer occurrence/schema evidence here; verify in `income-modeling-eph`, do not invent filename compatibility. |
| `fitted_RF/clf1_<year>_ARG`, `clf2`, `clf3`, quarterly `clf4` | immutable model output release, preferably predictions not pickle/joblib models | **requires migration** | Stop loading upstream serialized models in this repo; join released predictions by stable person ID. |
| current `modelos/clf*` versus legacy `fitted_RF/clf*` directory | model release manifest | **broken or unavailable** | Neither sibling directory exists here; no deterministic directory rename proves model equivalence. |
| `RFC1..RFC4_<frac>_<date>_ARG.csv` | released person-income table | **compatible after deterministic adapter**, conditional | Adapter may rename `ID→sample_person_id`, `P47T→income_value` only after manifest confirms transform/reference and ID namespace. RFC1–3 are not poverty inputs. |
| `AGLO_rk`, `Reg_rk` extensionless sibling files | upstream preprocessing/model features in release provenance | **requires migration** | Remove from poverty consumer; never regenerate mean-filled ranks here. |
| mutable `CB_Reg_defl_Q.csv` and local `CB_Reg_defl.csv`, `CBA_regional.csv`, `CBT_regional.csv` | pinned regional-basket artifact | **unresolved** | Names do not establish equal units/frequency/method. Require producer manifest. |
| mutable `indice_precios_M.csv` and several local IPC files | pinned IPC artifact | **requires migration** | Declare series/base/output month; remove `datetime.today()` dependency. |
| `table_f<FRAC>_<YEAR>_ARG.csv` plus locally generated `ID` | versioned Census sample | **compatible after deterministic adapter**, conditional | Require seed, weight, stable IDs and sample manifest; do not infer population weight as `1/FRAC` without approval. |
| historical `personas_ingresos_f...`, `pobreza_hogares_f...`, `hogares_geo_f...` | current `individual_income_sample...`, `household_poverty_sample...`, `geo_households_sample...` | **historical only** | Readers/writers already disagree across docs/comments; Batch 2 defines new bundle names rather than supporting both. |
| hard-coded 2003–2025 ranges, stage-4 2023–2025, and stage-5 `FRAC=0.05` | one manifest period/fraction | **broken or unavailable** | Pass one validated run manifest; reject cross-artifact mismatch. |

## 6. Expected schemas and lineage by stage

### Stage 1 — Census adaptation (move out of poverty path)

- **Entity/key:** person; current `ID` is expected unique, with
  `HOGAR_REF_ID` many-to-one and `RADIO_REF_ID` many-to-one. No assertions exist.
- **Required inputs:** Census housing/person fields used by `x_cols1` (`IX_TOT`,
  `P02`, `P03`, `V01`, `H05`–`H16`, `PROP`, `P05`, `P07`–`P10`, `CONDACT`),
  geography IDs, plus `AGLO_rk` and `Reg_rk`.
- **Generated locally:** renamed `IX_TOT`, `ANO4`, transformed Census variables,
  `Region`, generated `ID`, rank fields.
- **Disposition:** sampling, feature engineering, ID generation, and ranks are
  upstream responsibilities. Missing domains and merge loss are unbounded.

### Stage 2 — income modeling (consume, do not preserve)

- **Entity/key:** person-quarter, `ID + Q`; expected unique but unchecked.
- **Inputs:** all `x_cols1`; stage targets `CAT_OCUP`, `CAT_INAC`, `CH07`;
  derived income classes; labor-benefit fields; final income variables including
  `P47T`; employment ratio.
- **Outputs:** RFC stage files indexed by `ID`; only RFC4 `ID,P47T` is read by
  poverty code.
- **Unit:** code implies final `P47T` is `log10(ARS + 1)`, but no manifest confirms
  price reference, winsorization, missingness, or projection status.
- **Disposition:** duplicated model execution. Batch 2 requires a released
  person-income contract and rejects null/nonfinite income or duplicate keys.

### Stage 3 — poverty-specific integration

- **Person input:** unique `sample_person_id, sample_household_id, period`, age
  `P03`, sex `P02`, education `P09/P10` only if reporting it, geography link, and
  income with explicit transform/unit/reference.
- **Adult-equivalence input:** unique and total mapping over declared sex/age
  domain; `CB_EQUIV >= 0`; current implicit merge keys must become explicit.
- **Basket input:** unique `period + region`, positive CBA/CBT, declared ARS
  reference; every included household region covered.
- **Generated:** person `P0910` (reporting only); per-person equivalent CBA/CBT;
  household `P47T_hogar`, `CBA`, `CBT`, `CB_EQUIV`, booleans, and signed gaps.
- **Household output key:** exactly one row per `sample_household_id + period`.
  Current formulas are `Pobreza = income < CBT`, `Indigencia = income < CBA`,
  `gap_pobreza = income - CBT`, `gap_indigencia = income - CBA`.
- **Missingness:** current inner merges drop unmatched records. Batch 2 must fail
  on missing adult-equivalence/basket/geography mappings and report counts.

### Stage 4 — aggregation

- **Inputs/keys:** unique person- and household-period tables joined to geography;
  declared `sample_weight` rather than inferred division by `FRAC`.
- **Universes:** persons, agglomerate persons, age 24+, households, poor
  households, indigent households. The current `P03 >= 24` label “M24” is
  semantically ambiguous and needs owner approval.
- **Output key:** `release_id, period, universe, geography_level, geography_id,
  observable, statistic`; `value`, `unit`, `price_reference`, numerator,
  denominator, and coverage should accompany it.
- **Disposition:** project-specific aggregations may remain; current wall-clock
  reflation and append/dedup behavior must not.

### Stage 5 — geography/publication

- **Input:** department aggregate with stable, type-normalized `DPTO`; one geometry
  per department in declared CRS.
- **Output:** optional GeoJSON with release metadata and only approved metrics.
- **Disposition:** bounded join/export adapter may remain. Geometry acquisition,
  repair, and Atlas/Mapbox deployment belong elsewhere.

## 7. Code disposition

Counts below classify **22 major logical units**, not lines or notebook cells.

| Disposition | Count | Units and conclusion |
|---|---:|---|
| Poverty-specific and preserve | 5 | explicit income transform adapter (after contract), adult-equivalent application, household aggregation, poverty/indigence comparisons, signed gaps |
| Versioned integration adapter needed | 5 | income/sample join, adult-equivalence lookup, basket lookup, stable geography lookup, output manifest/bundle |
| Duplicated preprocessing; defer upstream | 4 | Census transformations, local IDs, rank creation/filling, employment adjustment |
| Duplicated model logic; consume release | 2 | four-stage prediction orchestration; model/feature declarations |
| Geography/publication-owned elsewhere | 3 | geometry loading/repair, GeoJSON production beyond bounded join, Mapbox/GCS upload |
| Exploratory/historical evidence | 2 | plotting/nowcasting notebooks; legacy notebooks/results |
| Obsolete or broken | 1 | current cross-notebook orchestration with absolute/sibling paths and incompatible fractions |

`canasta`, `calculate_poverty_metrics`, and the poverty portion of
`ingresos_a_metricas_pobreza` contain the core scientific behavior. They should be
ported only after human approval and tests. `personas_ingresos_por_trimestre` is an
adapter, while prediction helpers, `variables.py`, and notebook 2 should disappear
from the future consumer execution graph. No code is moved or deleted in Batch 1.

## 8. Candidate scientific invariants

| Invariant | Evidence status | Batch 2 treatment |
|---|---|---|
| Person, household and period keys are non-null; person-period is unique; every person maps to exactly one household. | proposed for human approval | Contract validation before calculation. |
| Joins conserve input persons/households; unmatched or multiplied rows are zero, otherwise fail with a report. | proposed for human approval | Required QA gate. |
| Household income and household thresholds equal sums of their included person components. | code-observed | Exact/tolerance checks. |
| `CBA <= CBT` for every region-period and equivalent household threshold. | method-documentation-derived | Requires methodological owner approval, then test. |
| `Indigencia ⇒ Pobreza`; categories are ordered and booleans are non-null. | method-documentation-derived | Requires approval; current comparisons imply it only when CBA≤CBT. |
| Equality to a threshold is not below the line (`<`, not `<=`). | code-observed | Explicit approval needed before freezing as test. |
| Gaps are signed `income - threshold`; classified-below households therefore have negative gaps. | code-observed | Preserve or approve a positive-shortfall rename/change. |
| Income is converted from its declared transform exactly once; all compared values share currency and price reference. | code-observed / proposed for human approval | Mandatory manifest and QA gate; catches current likely double exponentiation. |
| Adult-equivalent lookup covers every included person and coefficients are finite/nonnegative. | proposed for human approval | Mandatory coverage/domain report. |
| Every household has exactly one region and every region-period has one basket row. | proposed for human approval | Mandatory coverage/uniqueness report. |
| Counts, weights, denominators and rates are finite/nonnegative; rates lie in `[0,1]`. | proposed for human approval | Mandatory aggregate QA. |
| Weighted totals are conserved between national output and mutually exclusive child geographies, within declared tolerance. | proposed for human approval | Report tolerance and exclusions. |
| Geography keys are string-normalized, vintage-stable, unique in geometry, and have complete join coverage. | proposed for human approval | Mandatory spatial QA. |
| Every record is labelled observed, derived, or projected; synthetic Census-year projections are never described as observations. | method-documentation-derived | Mandatory metadata and limitations language. |
| Re-running the same release inputs/config produces byte-equivalent tabular values and does not append duplicates. | proposed for human approval | Reproducibility check. |

No proposed or documentation-derived invariant is a validated methodological rule
until Matías (or the designated scientific owner) approves it.

## 9. Proposed Batch 2 vertical slice (specification only)

### Slice identity

`poverty-department-2024q1-census2010-sample-v0` is the smallest credible
integration exercise. The name is provisional and must not be represented as an
official or current poverty estimate.

| Choice | Bounded specification |
|---|---|
| Period | `2024-02-15` only. **Human checkpoint:** approve the period and confirm upstream coverage. |
| EPH/preprocessing | one immutable `artifact:research.eph-annual-input@1` 2024 release referenced by the model manifest; not read directly by this repo. |
| Income | one immutable `artifact:research.eph-model-output@1` release for the selected sample/period, or an explicitly approved deterministic baseline. Must declare `income_transform`, ARS price reference, training/preprocessing IDs and model QA. |
| Census | one seeded, immutable CPV-2010 person/household sample release at a single fraction (provisionally 0.02), with stable IDs and weights. No regeneration in this repo. |
| Geography | department (`DPTO`) table only; optional department GeoJSON using a pinned 2010 geometry release. Agglomerate and electoral outputs excluded. |
| Prices/baskets | pinned regional CBA/CBT release for the same period and monetary reference as income. No `today` IPC. If alignment is impossible, stop. |
| Definition | current code-observed household rule: sum person income and equivalent thresholds; below CBT = poverty, below CBA = indigence; strict `<`; signed gaps. **Human checkpoint:** approve every rule. |
| Universes | households and persons living in classified households. Exclude M14/M24, employment, electoral, nowcast and subgroup publication. |
| Tabular bundle | `household_classification.parquet`, `department_summary.parquet`, `national_summary.parquet`, `manifest.json`, `qa.json`, `limitations.md`, `checksums.sha256`. |
| Spatial bundle | optional `department_summary.geojson`; omit rather than substitute unverified geometry. |

### Required QA/limitations report

The run must report input IDs/digests, software environment, key uniqueness,
missingness, join cardinality/coverage, transform and monetary-reference checks,
regional basket coverage, CBA/CBT ordering, category ordering, weighted totals,
department reconciliation, nonfinite/negative domains, reproducibility, and every
approved invariant. Limitations must state that Census 2010 is a synthetic/sample
frame, income is model-derived, outputs are research estimates, and no official
poverty statistic or present-day population estimate is produced.

### Stop gates

Do not implement or execute the slice until the scientific owner approves the
period, sample/weight policy, model release adequacy, adult-equivalence table,
basket/price policy, strict comparison, gap sign, and geography vintage. Stop on
any ID mismatch, missing manifest, transform ambiguity, monetary-reference
mismatch, incomplete mapping, or unexplained row loss.

## 10. Ordered adapter and migration backlog

| # | Source → target contract; affected code | Acceptance evidence | Owner / automation | Dependencies |
|---:|---|---|---|---|
| 1 | Producer manifests → one slice lock manifest; new Batch-2 adapter/config, replacing notebook constants | JSON-schema-valid manifest pins IDs, digests, period, fraction, units and references; rejects mismatch | Producers + Matías decisions; Codex mechanical after contracts | Other Batch-1 producer packets |
| 2 | Census sample release → normalized person/household tables; replaces notebook 1 and `transform_censo_data`/local ID path | uniqueness, seed/config, schema/domain, weight and geography coverage report | Sampler owner; Codex adapter mechanical; Matías approves weights/projection | Census sampler/geography packets |
| 3 | Income-model output → normalized person income; replaces notebook 2, `variables.py`, prediction helpers and RFC path | 1:1 sample-ID join; model/preprocessing provenance; transform/reference and QA declared | income-modeling-eph owner; Codex adapter mechanical; Matías accepts adequacy | EPH/model packet |
| 4 | Approved `adulto_eq` release → explicit sex/age lookup; affects `canasta` | total unique domain coverage and coefficient provenance | Matías methodological decision; Codex implementation | none after decision |
| 5 | Regional basket release → normalized region-period thresholds; affects `canasta` | unique complete region-period keys, positive values, CBA≤CBT if approved, shared monetary reference | Basket producer + Matías policy; Codex adapter | basket/price packet |
| 6 | Normalized persons/income/thresholds → household classification; ports `ingresos_a_metricas_pobreza` and `calculate_poverty_metrics` | approved invariants, golden hand-calculated fixture, zero silent row loss | Matías approves method; Codex implements | 1–5 |
| 7 | Household classification + sample weights → national/department summaries; replaces notebook 4 | numerator/denominator tables reconcile and reruns do not duplicate; no wall-clock input | Matías approves weighting; Codex implements | 6 + geography reference |
| 8 | Department summary + pinned geometry → optional GeoJSON; bounds notebook 5 | 100% key join or documented exclusion, valid CRS/geometries, tabular/spatial values agree | Geography owner; Codex adapter mechanical | geography packet, 7 |
| 9 | All outputs → release QA/limitations/checksum bundle | clean-room run from pinned inputs; checksums and invariant statuses recorded | Codex mechanical; Matías signs scientific report | 1–8 |
| 10 | Legacy notebooks → historical-only documentation; no deletion in this packet | canonical Batch-2 command no longer imports/runs notebooks 1–2 or deployment notebooks | Repository owner; Codex mechanical after successful slice | 9 |

### 10.1 Sprint-zero handoff: process the backlog without waiting on code design

The first three backlog items can start as soon as producers answer a small,
explicit contract request. To avoid another discovery round, this section freezes
the **consumer side** of that request. It does not select methodology or assert
that an upstream release exists.

#### Work lanes and merge order

| Lane | Can start now | Must wait for | First mergeable evidence |
|---|---|---|---|
| A — release lock and validation | Define the lock schema, path safety, digest syntax, cross-artifact period/sample checks, and negative fixtures. | Nothing for structure; real release IDs for an executable lock. | A validator rejects `latest`, mutable URLs, missing digests, period mismatch, sample-ID namespace mismatch, and unknown income transform. |
| B — Census adapter | Define canonical person/household columns, uniqueness/cardinality checks, and an adapter interface. | Sampler manifest, stable ID namespace, seed/config, weights, and permitted test fixture. | A tiny synthetic fixture adapts with no row loss; duplicate person IDs and orphan households fail. |
| C — income adapter | Define canonical income columns and transform/reference checks. | Model-output manifest, ID namespace, target period, transform, monetary reference, and approved non-sensitive fixture. | A tiny synthetic fixture joins 1:1; duplicate/missing IDs, unknown transform, and reference mismatch fail. |
| D — method tables | Profile schemas and define explicit join keys without changing values. | Provenance and approval for adult equivalence and regional baskets. | Coverage reports exist; no implicit `DataFrame.merge` keys remain in the proposed interface. |
| E — poverty kernel | Prepare hand-calculated fixtures for strict comparison, adult-equivalent sums, and signed gaps. | Approval of rules and completion of B–D. | A pure, side-effect-free kernel passes the approved golden fixture. |

Merge order is **A → B and C in parallel → D → E**. Geography and aggregation
must not block the household kernel and should follow only after the kernel contract
is stable.

#### Proposed repository layout for the first implementation PR

The following paths are reserved by this specification; they are not created in
Batch 1 because no executable producer contract is available yet.

```text
contracts/poverty-slice-lock.schema.json
contracts/census-sample.schema.json
contracts/person-income.schema.json
contracts/regional-baskets.schema.json
src/poverty_pipeline/contracts.py
src/poverty_pipeline/adapters/{census,income,baskets}.py
src/poverty_pipeline/kernel.py
tests/fixtures/contracts/{valid,invalid}/
tests/fixtures/golden/household_classification.csv
tests/test_contracts.py
tests/test_adapters.py
tests/test_kernel.py
```

The implementation should use a small package rather than importing notebook
state. Contract validation must run before pandas/polars loads large artifacts,
and the kernel must not perform network access, discover sibling paths, consult the
wall clock, or write outputs.

#### Slice-lock contract (consumer-owned)

This is the minimum instance shape for backlog item 1. A real lock replaces every
`PENDING_*` value and must contain no floating branch, `latest` alias, or mutable
raw URL.

```yaml
schema_version: 1
slice_id: poverty-department-2024q1-census2010-sample-v0
period: 2024-02-15
geography_level: department
artifacts:
  census_sample:
    artifact_id: PENDING_CENSUS_RELEASE
    manifest_uri: PENDING_IMMUTABLE_URI
    sha256: PENDING_64_HEX_DIGEST
    sample_id_namespace: PENDING_NAMESPACE
  income_predictions:
    artifact_id: PENDING_INCOME_RELEASE
    manifest_uri: PENDING_IMMUTABLE_URI
    sha256: PENDING_64_HEX_DIGEST
    sample_id_namespace: PENDING_SAME_NAMESPACE
  adult_equivalence:
    artifact_id: PENDING_APPROVED_RELEASE
    manifest_uri: PENDING_IMMUTABLE_URI
    sha256: PENDING_64_HEX_DIGEST
  regional_baskets:
    artifact_id: PENDING_BASKET_RELEASE
    manifest_uri: PENDING_IMMUTABLE_URI
    sha256: PENDING_64_HEX_DIGEST
policy:
  income_transform: PENDING_ONE_OF_linear_ars_log10_ars_plus_1
  monetary_reference: PENDING_EXACT_REFERENCE
  threshold_operator: PENDING_APPROVAL_FOR_strict_lt
  gap_definition: PENDING_APPROVAL_FOR_income_minus_threshold
  sample_weight_policy: PENDING_APPROVAL
optional:
  department_geometry: null
```

The validator must compare, not merely parse, the manifests: slice period equals
income and basket period; Census and income ID namespaces match; income and baskets
share the approved monetary reference; all artifact IDs are immutable; declared
files have SHA-256 digests; and optional geometry vintage matches the selected
geography policy. `PENDING_*` is valid only in a planning example and must fail an
execution lock.

#### Canonical adapter tables

These are deliberately narrower than the legacy tables. Additional producer
columns may pass through a staging layer but cannot become implicit kernel inputs.

**`persons`**

| Column | Type/domain | Constraint |
|---|---|---|
| `sample_person_id` | non-empty string | unique and stable within `sample_id_namespace` |
| `sample_household_id` | non-empty string | foreign key to `households` |
| `sex_code` | producer code plus dictionary | non-null and covered by adult-equivalence lookup |
| `age_years` | integer, `>= 0` | non-null and covered by adult-equivalence lookup |
| `radio_2010_id` | zero-preserving string | non-null; maps to one department |
| `sample_weight` | finite number, `> 0` | policy and calibration vintage declared |

**`households`**

| Column | Type/domain | Constraint |
|---|---|---|
| `sample_household_id` | non-empty string | unique |
| `department_2010_id` | zero-preserving string | exactly one per household |
| `region_id` | controlled string | exactly one per household and covered by basket release |

**`person_income`**

| Column | Type/domain | Constraint |
|---|---|---|
| `sample_person_id` | non-empty string | unique for selected period and complete under approved join policy |
| `period` | ISO date | exactly the locked period |
| `income_value` | finite number | transform declared in manifest; converted exactly once |
| `income_transform` | `linear_ars` or `log10_ars_plus_1` | one value matching the lock |
| `monetary_reference` | controlled string | exactly matches baskets or approved deterministic conversion |
| `classification` | `observed`, `derived`, or `projected` | required; expected `projected` for model output |
| `model_release_id` | immutable identifier | matches the locked artifact |

**`regional_baskets`**

| Column | Type/domain | Constraint |
|---|---|---|
| `period` | ISO date | locked period only |
| `region_id` | controlled string | unique with `period`; complete over households |
| `cba_per_adult_equivalent` | finite number, `> 0` | same monetary reference as income |
| `cbt_per_adult_equivalent` | finite number, `> 0` | ordering check is gated on approval |
| `monetary_reference` | controlled string | release metadata and row values agree |

#### Producer request template

Send this exact request independently to the sampler, income-model, and basket
owners; an answer may be “not available”, but omitted metadata must not be guessed.

```text
Please provide one immutable candidate release for period 2024-02-15 and the
provisional CPV-2010 sample namespace. Include: artifact/release ID; immutable URI;
SHA-256 per file; schema and data dictionary; entity and unique keys; period and
geography vintage; units and monetary reference; observed/derived/projected label;
missingness/domain guarantees; producer commit; environment or methodology ID;
and a small non-sensitive contract fixture. For Census, also provide seed/config,
household relation, and weight semantics. For income, also provide transform,
sample-ID namespace, training/preprocessing release IDs, and QA. For baskets, also
provide adult-equivalent unit, region dictionary, source/methodology, and coverage.
Do not provide a branch URL, latest alias, or undocumented sibling path.
```

#### Mechanical acceptance matrix

| Check | Required result before kernel work | Failure action |
|---|---|---|
| Manifest schema and digests | All required fields present; every digest matches. | Stop; producer republishes metadata/artifact. |
| Immutability | URI resolves to a version/release; no branch or `latest`. | Stop; request immutable release. |
| Period/reference agreement | Exact period and monetary-reference equality, or an approved named conversion. | Stop for Matías/producer decision. |
| ID compatibility | Census and income declare the same namespace; income IDs satisfy approved join cardinality. | Stop; no fuzzy or positional matching. |
| Census relations | Unique persons/households, no orphan persons, one household geography, positive weights. | Stop; producer fixes release or documents approved exclusions. |
| Lookup coverage | Every person has one adult-equivalence row; every household has one basket region-period. | Stop; never inner-join away misses. |
| Determinism | Same fixture and lock yield identical sorted tables and QA JSON. | Stop; remove wall-clock/order/random behavior. |

#### Decisions queued for Matías

The following compact decision record is the only methodological blocker list for
the first kernel. Each answer should include approver, date, rationale, and the
method/release ID it applies to.

1. Confirm or replace `2024-02-15` and the 0.02 Census-sample proposal.
2. Approve sample weights (producer weights versus `1/FRAC`) and target population.
3. Accept a named income-model release as adequate for this research slice.
4. Approve the adult-equivalence source/version and exact age/sex domains.
5. Approve the regional basket release and monetary-reference policy.
6. Confirm strict `<` at CBA/CBT equality and signed `income - threshold` gaps.
7. Confirm department-2010 geography and whether optional GeoJSON is desired.

#### Definition of ready for the first implementation PR

Backlog item 1 is ready when the lock structure above is accepted. Items 2 and 3
are ready only when at least one producer supplies a manifest and safe fixture.
The household kernel is ready only when all seven decisions are recorded and the
three required input contracts pass. Until then, useful work is limited to
contract/fixture validators—never a live-data run or methodological default.

## 11. Smoke versus validation

`make smoke` is correctly interpreted only as **repository-structure smoke**. It
checks that five notebooks, two helpers and one local CSV exist, that each notebook
contains the text `FRAC`, and that notebook 3 contains an output-name marker. It
does **not** audit dependency contracts, import/execute code, verify schemas,
reconcile units, test scientific invariants, or validate results.

The three distinct gates for future work are:

1. **Repository-structure smoke:** current `make smoke` marker/file check.
2. **Dependency-contract audit:** future manifest/schema/checksum validation before
   loading data.
3. **Scientific execution:** separately approved Batch-2 run and QA report.

A pass at one gate must never be reported as a pass at the next.

## 12. Completion record

Commands used for this audit were read-only except for replacing this document:

```text
find .. -name AGENTS.md -print
git status --short --branch
sed -n ... README.md SYSTEM.yaml docs/*.md Makefile scripts/smoke_repo.sh .gitignore
find notebooks data -maxdepth ... -type f
python (stdlib JSON extraction of code cells to /tmp/nbcode)
rg / git grep searches for paths, reads/writes, parameters, legacy names and functions
make smoke
git diff --check
```

The audit found the current/sibling/local/cloud/raw-GitHub dependencies listed
above, the absent `EPHARG_annual_input_*` assumption, legacy `EPHARG_train*` and
model paths, incompatible fraction/year parameters, mutable price references, and
a likely double income exponentiation. The disposition covers 22 major units (5
preserve, 5 adapters, 4 preprocessing, 2 model, 3 geography/publication, 2
historical, 1 broken). Fifteen candidate invariants remain explicitly
evidence-labelled, with methodological choices gated for approval.

This packet specifies but does not run the one-quarter department slice. It makes
no poverty estimate and confirms that no full poverty computation, training, data
refresh, deployment, cloud upload, Mapbox operation, or publication occurred.
