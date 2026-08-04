# Codex work packet — Batch 4: first visible poverty release

## Mission

Turn the components already merged into this repository into one executable,
inspectable release path that produces poverty tables, aggregates, plots and
map-ready data.

This is not a broad notebook modernization. It is an integration and evidence
packet whose first objective is to make the system visibly run end to end, expose
broken seams and create a release that a human can inspect.

The work has two ordered targets:

1. a complete deterministic synthetic release that proves every stage is wired;
2. a candidate release from matching local historical/real artifacts, when those
   artifacts actually exist and can be identified without guessing.

Never describe a synthetic or legacy-candidate output as an official poverty
estimate.

## Read first

Read the current `main` after merged PRs 7–12, especially:

- `README.md` and `SYSTEM.yaml`;
- `contracts/poverty-slice-lock.schema.json`;
- `src/poverty_pipeline/contracts.py`;
- `src/poverty_pipeline/planning.py`;
- `src/poverty_pipeline/cli.py`;
- `src/poverty_pipeline/adapters/`;
- `src/poverty_pipeline/science/household_poverty.py`;
- `src/poverty_pipeline/aggregation.py`;
- `src/poverty_pipeline/packaging.py`;
- `src/poverty_pipeline/publication/geojson.py`;
- `notebooks/released_outputs.py`;
- `data/info/adulto_eq.csv`;
- tests and fixture releases;
- the consumer-lineage audit in
  `docs/CODEX_BATCH1_POVERTY_CONSUMER_LINEAGE.md`.

Do not execute the historical notebooks as a production pipeline.

# Part A — reconcile the current internal contract drift

The repository currently contains strong components that do not yet compose.
Resolve these contradictions before introducing new features.

## A1. Implement the documented command

The README and system declaration advertise:

```bash
PYTHONPATH=src python -m poverty_pipeline run-lock <lock>
```

but `src/poverty_pipeline/cli.py` currently exposes only `validate-lock` and
hard-codes `contracts_only` behavior.

Implement `run-lock` as the canonical orchestrator for `mode: poverty_release`.
Preserve `validate-lock` and `contracts_only` exactly as a non-scientific path.

The `run-lock` sequence must be explicit:

```text
validate lock and all pins
resolve immutable release directories
build metadata-only execution plan
materialize canonical input tables
run adapter QA
construct scientific dependency contract and policy objects
run the pure household poverty kernel
build classified person and household tables
aggregate approved estimands
package an immutable release
optionally create local department GeoJSON
render bounded inspection outputs
verify the completed release
```

No stage may discover a sibling checkout, call the network, load an upstream model
binary or consult the wall clock.

## A2. Make the validator support the schema it declares

`contracts/poverty-slice-lock.schema.json` describes both `contracts_only` and
`poverty_release`, while `validate_lock()` currently accepts only
`contracts_only` and resolves only Census and income fixtures.

Implement mode-specific validation and resolution for exactly four direct
scientific artifacts:

```text
research.census-sample/v1
research.person-income-predictions/v1
research.poverty-adult-equivalence/v1
research.regional-baskets/v1
```

Compare identities rather than merely parsing documents:

- release ID and manifest SHA-256;
- allowed status;
- selected period;
- exact Census/income sample-ID namespace;
- CPV-2010 geography vintage;
- linear-ARS output after the income adapter;
- income/basket currency and monetary-reference equality;
- adult-equivalence sex and age domains;
- basket region-period coverage;
- approval and policy identifiers;
- declared upstream EPH/model lineage.

Warnings and limitations may remain on a candidate release. They must be copied to
run QA and limitations. They are not universal blockers.

Hard failures remain:

- corrupt or tampered files;
- unsafe paths;
- wrong artifact type;
- incompatible namespace, period or monetary identity;
- duplicate or missing keys that prevent the requested calculation;
- nonfinite values;
- double transformation;
- nondeterministic output from the same lock;
- an incomplete specifically requested region-period slice.

A finite negative value on a logarithmic source scale is not itself a hard
failure. It may produce a warning. The kernel still requires finite, nonnegative
linear income after the declared conversion.

## A3. Choose one truthful bundle contract

The current surfaces disagree:

- the README and lock schema describe named Parquet roles and
  `release_manifest.json`;
- `notebooks/released_outputs.py` expects those Parquet roles;
- `poverty_pipeline.packaging` currently writes `estimates.csv`, `manifest.json`,
  `qa.json`, `limitations.md` and checksums.

Do not preserve both incompatible contracts.

For v1, prioritize availability and a dependency-light path:

- CSV is the required canonical tabular representation;
- Parquet may be an optional derivative when a verified engine is available;
- manifest file roles, not filename guessing, are authoritative;
- `notebooks/released_outputs.py` must read roles from the release manifest and
  support the required CSV bundle;
- the packager must emit the full scientific outputs, not only tidy aggregates.

The required release roles are:

```text
household_classification
person_classification
aggregates_tidy
department_summary
national_summary
release_manifest
run_qa
limitations
checksums
```

Optional roles:

```text
department_spatial
plot_national_rates
plot_department_rates
plot_gap_distribution
plot_map_preview
```

Every file must be in the checksum inventory. The manifest must identify all four
direct inputs, upstream lineage, policies, software commit and output roles.

# Part B — publish the adult-equivalence artifact already present

`data/info/adulto_eq.csv` is an existing methodological input. Package its current
bytes without changing a coefficient as:

```text
research.poverty-adult-equivalence/v1
```

The release must include:

- immutable release ID;
- source-file hash;
- normalized table or an explicitly declared unchanged source table;
- sex-code dictionary;
- inclusive age-domain declaration;
- provenance and methodology status;
- QA and limitations;
- shared manifest envelope.

Verify mechanically:

- unique `(sex_code, age_years)` cells;
- both declared sex domains;
- complete age coverage from 0 through 110 for each sex;
- finite nonnegative coefficients;
- deterministic ordering;
- no silent filling or interpolation.

Do not invent an INDEC document/version if the repository does not prove it.
Use a truthful candidate methodology identifier and record the missing documentary
provenance as a warning.

# Part C — execute a complete synthetic release

Build a `poverty_release` synthetic lock using copied immutable fixture releases
for:

- Census persons/households;
- person-income predictions;
- the adult-equivalence release;
- a complete six-region basket fixture;
- a tiny CPV-2010-like department geometry fixture.

The synthetic fixture must exercise:

- multiple persons per household;
- at least three departments and two basket regions;
- poor, indigent and non-poor households;
- equality with a threshold under both comparison-policy tests;
- positive and zero gaps under both sign conventions;
- log and linear source prediction fixtures before the final linear-ARS kernel;
- weighted household and person rates;
- national-to-department reconciliation;
- map join coverage;
- warnings that do not block candidate execution.

Add a governed synthetic execution command, for example:

```bash
make poverty-release-smoke
```

It must:

1. build or copy the fixture releases;
2. execute `run-lock`;
3. verify the release checksums and manifest;
4. load released tables through `notebooks/released_outputs.py`;
5. render the inspection outputs;
6. rerun in a clean destination and prove deterministic tabular values.

# Part D — create visible inspection products

Add a read-only release-inspection command such as:

```bash
PYTHONPATH=src python -m poverty_pipeline inspect-release <release-dir>
```

It must never rerun science. It reads only an immutable output release.

Produce at minimum:

1. national poverty and indigence rates for households and persons;
2. a ranked department table with numerator, denominator, rate and coverage;
3. a department poverty/indigence comparison plot;
4. a household income-versus-threshold or gap-distribution plot when the release
   contains the required household fields;
5. map-ready department GeoJSON;
6. a static map preview when the plotting/geospatial environment supports it;
7. a compact HTML or Markdown release summary linking every output, limitation
   and input identity.

Use noninteractive plotting and deterministic filenames. A missing optional map
renderer is a warning; missing map-ready GeoJSON when requested is a hard failure.

# Part E — recover local historical artifacts before recomputing

The quickest route to actual visible data may be a matching historical bundle
already present outside Git.

Perform a read-only inventory of likely locations, but only when they exist:

```text
data/Pobreza/
data/results/
data/geojson/
data/yr_samples/
data/Fitted_RF/
/media/matias/Elements/suite/poblaciones/
/media/matias/Elements/suite/out/
```

Also inspect any repository-local paths referenced by historical notebooks.
Do not assume these exact absolute paths exist on every machine.

Create a machine-readable inventory recording for each candidate artifact:

- path and SHA-256;
- byte size;
- columns and inferred entity;
- row count;
- sample fraction;
- period;
- ID columns and namespace evidence;
- income transform evidence;
- monetary-reference evidence;
- matching Census/RFC stage family;
- geography coverage;
- whether it is safe to package without mutating the original.

Do not copy raw Census microdata or large local artifacts into Git.

## E1. Prefer an existing matched candidate

Search first for a pair such as:

```text
Census sample / population table
RFC4 or final person-income output
```

that demonstrably shares:

- exact person IDs;
- sample fraction;
- selected period;
- row coverage;
- income-transform convention.

If a viable pair exists, package it into local immutable candidate releases using
the shared artifact envelope. Preserve all limitations and classify uncertain
historical provenance as warnings.

Then run the first local candidate poverty release using:

- the matched Census sample;
- the matched person-income candidate;
- the newly packaged adult-equivalence artifact;
- the copied 2024-Q1 basket candidate when available;
- department geography when compatible.

The result must be labelled `candidate` or `legacy_candidate`, never approved or
official.

## E2. If no matched pair exists

Do not fabricate a result or positionally join rows.

Emit:

```text
build/recovery/local-artifact-inventory.json
build/recovery/LOCAL_ARTIFACT_RECOVERY_REPORT.md
```

The report must state exactly which producer packet is required next:

- deterministic Census sample release;
- Census-indexed income prediction release;
- both;
- or only an ID/monetary adapter.

# Part F — production hardening after visible execution

Once the full synthetic release works and a local candidate has either succeeded
or produced a precise blocker report, add the bounded production layer:

- unit and end-to-end tests for `run-lock`;
- contract tests using copied producer releases;
- deterministic release verification;
- CI for the synthetic release only;
- no live data, credentials or large artifacts in CI;
- one command that reports available local release directories and their status;
- release-index JSON/CSV containing release ID, period, status, location,
  limitations and verification result;
- clear separation of computation, inspection and publication commands.

Do not reactivate Mapbox uploads, GCS uploads or historical notebooks.

# Required tests

Cover at minimum:

- schema says `poverty_release` and runtime accepts it;
- `contracts_only` remains non-scientific;
- all four direct releases are pinned and verified;
- candidate warnings propagate without becoming hard failures;
- namespace/period/monetary mismatches fail;
- adult-equivalence coverage and basket coverage fail when incomplete;
- log conversion occurs exactly once;
- household sums and classifications match a hand-calculated fixture;
- indigence implies poverty when CBA <= CBT;
- weighted person and household aggregates reconcile;
- package and loader agree on roles, names and formats;
- release destination is immutable;
- checksum tampering fails;
- plots and map-ready GeoJSON are generated from released tables only;
- repeated execution produces equivalent values;
- no production code imports or executes historical notebooks.

# Non-goals

- No new poverty methodology.
- No automatic scientific approval.
- No application of the EPH flagship model directly to Census rows.
- No fuzzy or positional ID joins.
- No source acquisition from mutable branch URLs.
- No public claim of current or official poverty.
- No Atlas deployment in this repository.
- No deletion of historical notebooks or local artifacts.

# Completion report

The final PR description must include:

- the reconciled canonical command and bundle contract;
- every contract drift fixed;
- synthetic release ID and exact output paths;
- plots, tables and GeoJSON produced;
- commands and tests run;
- adult-equivalence release identity and unresolved provenance;
- local artifact inventory findings;
- whether a real/legacy candidate poverty release was produced;
- if not, the precise missing producer artifact;
- all warnings and hard failures encountered;
- confirmation that no official poverty claim or remote publication occurred.
