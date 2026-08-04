# Codex work packet — Portfolio Batch 4 sprint zero: contracts and adapters

## Mission

Implement the consumer-owned contract layer for one bounded poverty research slice without running a real poverty estimate.

This packet executes only the immediately actionable portion of the merged consumer-lineage backlog:

```text
A. immutable slice-lock and release validation
B. Census person/household adapter on synthetic fixtures
C. person-income adapter on synthetic fixtures
```

It prepares later basket/adult-equivalence adapters and the pure household poverty kernel, but it must not choose unresolved methodology or claim that the current flagship model can already score a Census sample.

## Portfolio naming

The existing audit describes the proposed poverty slice as a local “Batch 2” slice. In the broader portfolio program:

- Portfolio Batch 2 freezes the flagship income model;
- Portfolio Batch 3 repairs price and basket release lineage;
- Portfolio Batch 4 produces the bounded poverty research slice.

This packet is Portfolio Batch 4 **sprint zero**.

## Read first

1. Read the full merged `docs/CODEX_BATCH1_POVERTY_CONSUMER_LINEAGE.md`.
2. Read `README.md`, `SYSTEM.yaml`, `Makefile`, structural smoke scripts, `docs/data.md`, `notebooks/funciones.py`, `notebooks/variables.py`, and the poverty-calculation notebook only as historical/method evidence.
3. Inspect current `income-modeling-eph` declarations read-only, including its preprocessing consumer contract and model target.
4. Read the shared artifact-envelope and validator behavior from producer release documentation, but do not import producer source packages.
5. Do not execute notebooks, download mutable URLs, load legacy model binaries, or discover sibling paths.

## Mandatory integration correction

The current flagship model target is:

```text
logP47T = log10(P47T)
```

Therefore the canonical transform vocabulary must include:

```text
linear_ars
log10_ars
log10_ars_plus_1
```

Rules:

- `log10_ars` means `log10(P47T)` and mechanically inverts as `10 ** value`;
- `log10_ars_plus_1` means `log10(ARS + 1)` and mechanically inverts as `10 ** value - 1`;
- they are incompatible transforms;
- no adapter may guess the transform from a filename or historical convention;
- conversion may occur exactly once and must be reported;
- mechanical inverse transformation does not by itself establish an unbiased expected income for poverty measurement.

The merged audit’s provisional two-value transform list is superseded by this packet.

## Scientific boundary

The current flagship model is trained and evaluated on EPH-derived rows. It does not yet prove compatibility with a CPV-2010 Census sample.

This packet must therefore support two separate artifact types:

```text
research.eph-income-model/v1
research.person-income-predictions/v1
```

The poverty consumer accepts only the second.

A person-income prediction release must already contain predictions indexed in the exact Census sample-ID namespace. The consumer must not:

- load the flagship model binary;
- generate Census features;
- translate EPH features to Census implicitly;
- invoke `income-modeling-eph`;
- positionally or fuzzily match people;
- assume the current model can score Census records.

For sprint zero, use synthetic prediction fixtures only.

# Required repository layout

Create a small package independent of notebook state, using approximately:

```text
contracts/research-artifact-manifest-v1.schema.json
contracts/poverty-slice-lock.schema.json
contracts/census-sample.schema.json
contracts/person-income-predictions.schema.json
src/poverty_pipeline/__init__.py
src/poverty_pipeline/contracts.py
src/poverty_pipeline/adapters/__init__.py
src/poverty_pipeline/adapters/census.py
src/poverty_pipeline/adapters/income.py
src/poverty_pipeline/cli.py
fixtures/releases/census-sample-fixture-v1/
fixtures/releases/person-income-fixture-v1/
fixtures/slice-locks/
tests/test_contracts.py
tests/test_census_adapter.py
tests/test_income_adapter.py
```

Adjust to repository conventions, but keep the implementation separate from notebooks.

# Phase A — slice lock and release validation

## A1. Shared envelope validation

Implement a standard-library preflight validator for copied release directories using:

```text
research-artifact-manifest/v1
```

It must validate before pandas/geopandas or other heavy readers are imported:

- manifest schema version;
- artifact type;
- release ID and immutable status;
- producer repository/commit metadata;
- safe relative paths;
- file and report existence;
- file/report sizes and SHA-256 hashes;
- compatibility declaration identity;
- requested release status/mode;
- period/vintage;
- expected upstream manifest identities;
- limitations and unresolved blockers where policy requires them.

Never accept:

- branch URLs;
- `latest` aliases;
- mutable raw-GitHub URLs;
- absolute paths;
- `..` path escapes;
- missing or non-hex checksums;
- an artifact type substituted merely because its columns resemble the expected table.

## A2. Slice-lock schema

Implement a validated lock containing:

- slice ID;
- selected period;
- geography level;
- Census sample artifact identity, manifest hash, and sample-ID namespace;
- person-income prediction artifact identity, manifest hash, and sample-ID namespace;
- adult-equivalence artifact placeholder;
- regional-basket artifact placeholder;
- optional geography artifact;
- approved execution policies;
- software/contract versions.

Planning examples may contain `PENDING_*`, but execution validation must reject them.

For sprint zero, support a mode such as:

```text
contracts_only
```

that validates Census and income fixtures while explicitly recording that adult equivalence, baskets, and poverty methodology are unresolved and no kernel execution is authorized.

## A3. Cross-artifact compatibility

The validator must compare, not merely parse:

- Census and income sample-ID namespaces;
- exact period compatibility;
- release statuses allowed by the requested mode;
- prediction transform vocabulary;
- monetary reference presence;
- person/household entity expectations;
- geography vintage where supplied;
- file roles and schema identities.

The fixture lock should be deterministic and content-addressed.

# Phase B — Census adapter

## B1. Input contract

Consume a versioned Census sample release containing separate person and household tables.

Canonical person columns:

```text
sample_person_id
sample_household_id
sex_code
age_years
radio_2010_id
sample_weight
```

Canonical household columns:

```text
sample_household_id
department_2010_id
region_id
```

Additional provenance columns may pass through only when explicitly declared.

## B2. Adapter behavior

The adapter must:

- validate the release before loading tables;
- preserve IDs as strings and retain leading zeroes;
- require unique person and household IDs;
- require every person to reference exactly one existing household;
- require one declared household geography and region;
- require finite positive sample weights;
- preserve deterministic row ordering;
- emit a bounded QA report;
- fail instead of silently dropping duplicate, orphaned, or unmapped records.

Do not generate IDs in the consumer.

## B3. Synthetic fixtures

Cover at least:

- valid multi-person households;
- leading-zero geographic IDs;
- duplicate person ID;
- duplicate household ID;
- orphan person;
- household with conflicting geography;
- missing/negative/nonfinite weight;
- tampered manifest/file;
- namespace mismatch.

# Phase C — person-income prediction adapter

## C1. Input contract

Consume a person-income prediction release with canonical columns:

```text
sample_person_id
period
prediction_value
prediction_transform
monetary_reference
classification
model_release_id
```

Required classification vocabulary:

```text
observed
derived
projected
synthetic
```

For model predictions, `projected` is the expected classification unless a more precise approved vocabulary is introduced.

## C2. Supported transforms

Implement explicit, separately tested conversion functions:

```text
linear_ars          → identity
log10_ars           → 10 ** value
log10_ars_plus_1    → 10 ** value - 1
```

Requirements:

- conversion occurs only when the lock explicitly requests linear ARS;
- source transform and output transform are recorded;
- output values must be finite and nonnegative under the selected contract;
- no automatic clipping;
- unknown transforms fail;
- a transform declared by rows must match the release manifest and slice lock;
- tests must detect double transformation.

Document retransformation limitations. Do not call the mechanical inverse an unbiased expectation.

## C3. ID join

The adapter must:

- validate the release before loading;
- require the exact Census sample-ID namespace;
- require unique person-period keys;
- require exact selected period;
- join by `sample_person_id` only;
- report missing Census predictions and extra prediction IDs;
- fail under the default strict policy on any missing, extra, duplicated, or multiplied ID;
- never use row order, names, demographic similarity, or fuzzy matching.

## C4. Synthetic fixtures

Cover:

- valid `linear_ars` predictions;
- valid `log10_ars` predictions;
- valid legacy `log10_ars_plus_1` predictions;
- exact mechanical inverse values;
- unknown transform;
- row/manifest transform disagreement;
- double-transform attempt;
- period mismatch;
- ID namespace mismatch;
- duplicate/missing/extra prediction IDs;
- negative/nonfinite converted income;
- tampered release.

# Phase D — prepare, but do not implement, method inputs

Define interfaces and schemas only for:

- adult equivalence;
- regional CBA/CBT baskets;
- optional geography.

Do not copy current local CSV values into a new authoritative release.

Create `docs/BATCH4_METHOD_INPUTS_REQUIRED.md` listing exactly what producer artifacts and Matías decisions are required before implementation:

1. selected slice period;
2. Census sample/weight policy;
3. accepted person-income prediction release and adequacy;
4. adult-equivalence source/version and domains;
5. regional basket release and monetary reference;
6. strict/equality threshold policy;
7. gap-sign definition;
8. department geography vintage and optional spatial output.

The household poverty kernel remains blocked until these are approved.

# Command surface

Provide commands equivalent to:

```bash
make contracts-check
make contracts-smoke
make adapters-smoke
python -m poverty_pipeline validate-lock fixtures/slice-locks/contracts-only.yaml
```

Keep existing `make smoke` clearly labeled as structural smoke. It must not be replaced by or confused with the new contract checks.

# Required QA artifacts

Fixture execution should emit deterministic QA JSON containing:

- selected release IDs and manifest hashes;
- input row counts;
- key uniqueness;
- foreign-key coverage;
- ID namespace;
- period;
- prediction transform and conversion count;
- missing/extra ID counts;
- geography/region coverage;
- output row counts and hashes;
- explicit `scientific_execution_performed: false`.

# Human checkpoints

Stop before:

- selecting or changing the real slice period;
- accepting a Census sample or weight policy;
- treating the flagship EPH model as Census-compatible;
- choosing a real person-income prediction release;
- accepting retransformed predictions for poverty measurement;
- approving adult equivalence or baskets;
- implementing threshold comparisons or gaps;
- running a real poverty estimate;
- producing public tables or GeoJSON.

# Non-goals

- No notebook execution or migration.
- No Census sampling.
- No model loading or inference.
- No EPH-to-Census feature alignment.
- No adult-equivalence or basket methodology.
- No household poverty kernel yet.
- No aggregation, statistics, mapping, publication, or deployment.
- No mutable URL access.
- No large real data committed to Git.

# Acceptance criteria

```text
a standard-library shared-envelope validator rejects unsafe/tampered releases
a deterministic contracts-only slice lock pins Census and income fixture releases
Census fixtures adapt to canonical person/household tables with strict relational QA
income fixtures support linear_ars, log10_ars, and log10_ars_plus_1 without ambiguity
log10(P47T) is never confused with log10(P47T + 1)
Census and income sample-ID namespaces must match exactly
no model binary or sibling repository is invoked
method inputs and seven-plus human decisions remain explicit blockers
all outputs state that no scientific poverty execution occurred
```

# Completion report

The final response and PR description must include:

- files/contracts implemented;
- exact fixture release IDs and hashes;
- commands and tests run;
- transform cases verified;
- ID and relational failures exercised;
- unresolved producer artifacts and human decisions;
- explicit confirmation that no model inference, real data, poverty kernel, aggregation, or publication occurred;
- a readiness statement for the next merge order: baskets/adult-equivalence adapters → approved pure kernel.
