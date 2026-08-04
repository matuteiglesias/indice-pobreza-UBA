# Codex work packet — Batch 1: audit the poverty workspace as a downstream consumer

## Mission

Map this repository's actual dependencies on EPH preprocessing, income models, prices, baskets, Census samples, geography, employment data, and crosswalks so Batch 2 can connect the flagship model without preserving hidden sibling paths or duplicated transformations.

This is a downstream-consumer and code-disposition audit. Do not modernize the full notebook pipeline or change poverty methodology in this packet.

## Why this matters

This repository is the broad legacy integration workspace where poverty measurement, income prediction, Census application, geospatial aggregation, and publication preparation became entangled. Its documentation names many legitimate upstream assets, but the current smoke check only verifies file presence and notebook markers.

The goal is to make its required inputs and poverty-specific authority explicit, then define one viable future vertical slice.

## Read first

1. Read every applicable `AGENTS.md` file.
2. Read `README.md`, `SYSTEM.yaml`, `docs/data.md`, maintenance documentation, `Makefile`, `scripts/smoke_repo.sh`, `notebooks/funciones.py`, `notebooks/variables.py`, and the ordered notebooks.
3. Inspect configuration, local/sibling paths, cloud-storage references, generated outputs, and `.gitignore` before executing anything.
4. Inspect `income-modeling-eph` read-only as the current authority for annual EPH preprocessing and income modeling.
5. Inspect `encuestador-de-hogares` read-only only to understand legacy names and assumptions still embedded here.
6. Inspect price, basket, geography, sampler, employment, and crosswalk repositories only as required to resolve concrete dependencies.

Do not treat the current README's broad aspirations as evidence that every pipeline is reproducible.

## Authority and boundaries

This repository should own:

- project-specific poverty measurement choices;
- combination of household income outputs with declared CBA/CBT thresholds;
- poverty/indigence classifications and gaps;
- project-specific aggregation and derived research outputs;
- the integration recipe for a selected research release.

It should not own:

- raw EPH acquisition;
- annual EPH preprocessing;
- income-model training infrastructure;
- official price or basket series;
- authoritative Census/IGN geometries;
- generic Census sampling;
- Atlas deployment.

## Required deliverables

### 1. Executable pipeline map

Create `docs/POVERTY_PIPELINE_CHARACTERIZATION.md` describing the real execution graph:

- notebook/module order;
- inputs read by every stage;
- outputs written by every stage;
- local, cloud, raw GitHub, and sibling-repository paths;
- parameters and global variables controlling year, quarter, fraction, geography, and output paths;
- hidden manual steps;
- expensive/destructive/networked behavior;
- currently executable stages versus historical or broken stages.

For each dependency, cite the exact code or configuration path.

### 2. Consumer dependency registry

Create a machine-readable registry with one entry per required input artifact. Include:

- consumer stage;
- current path/reference;
- proposed artifact identity;
- producer repository;
- required version/vintage;
- required files;
- expected schema and key columns;
- unit and frequency;
- freshness requirement;
- whether optional or mandatory;
- current availability and verification status;
- fallback behavior;
- unresolved assumptions.

At minimum investigate:

- annual preprocessed EPH inputs;
- income-model outputs;
- Census samples;
- Census/IGN geometries and reference tables;
- EPH agglomerate/region mappings;
- IPC/monetary reference;
- CBA/CBT regional thresholds;
- employment series;
- electoral crosswalks only where actually used.

Do not preserve a sibling path as the contract.

### 3. Legacy-name compatibility audit

Search for all assumptions about:

- `EPHARG_train*`;
- current `EPHARG_annual_input_*` naming;
- old model filenames and directories;
- old geographic rank files;
- old price/basket filenames;
- hard-coded year and quarter ranges.

Create `docs/LEGACY_INPUT_COMPATIBILITY.md` mapping old names and schemas to current or proposed release artifacts. Classify each use as:

```text
compatible as-is
compatible after deterministic adapter
requires migration
historical only
broken or unavailable
unresolved
```

### 4. Expected schema report

For each notebook stage, generate a report of:

- required columns;
- keys and expected uniqueness;
- entity level: person, household, geography, or period;
- units and monetary reference;
- accepted missingness/domains;
- columns generated locally;
- columns imported from preprocessing/model outputs;
- columns that duplicate upstream transformations.

Explicitly separate the current preprocessing authority in `income-modeling-eph` from poverty-specific calculations here.

### 5. Code disposition report

Create `docs/POVERTY_CODE_DISPOSITION.md` classifying major functions, notebook sections, and generated artifacts as:

- poverty-specific and worth preserving;
- integration adapter needed for a versioned upstream artifact;
- duplicated preprocessing that should defer to `income-modeling-eph`;
- duplicated model logic that should consume a model release;
- geography/export logic better owned by a geography or publication component;
- exploratory/historical evidence;
- obsolete or broken;
- unresolved.

Do not move or delete code in this packet.

### 6. Scientific invariant inventory

Create `docs/POVERTY_INVARIANTS.md` listing candidate invariants that future implementation must test, such as:

- household/person aggregation consistency;
- poverty and indigence category exclusivity and ordering;
- adult-equivalent threshold behavior;
- monetary reference compatibility between income and baskets;
- regional threshold coverage;
- population/weight conservation through aggregation;
- nonnegative counts and gaps where methodologically required;
- stable geography keys;
- explicit observed/derived/projected classifications.

Label each invariant as:

```text
code-observed
output-observed
method-documentation-derived
proposed for human approval
```

Do not convert proposed methodological rules into tests without approval.

### 7. One future vertical-slice specification

Create `docs/BATCH2_POVERTY_VERTICAL_SLICE.md` specifying the smallest credible future integration run. It should select:

- one supported EPH/preprocessing release;
- one income-model release or bounded baseline;
- one Census sample/release;
- one geographic level;
- one declared price and basket policy;
- one period;
- one poverty/indigence definition;
- one output table bundle;
- one optional bounded GeoJSON output;
- one QA and limitations report.

This file is a specification only. Do not execute the full slice now.

### 8. Adapter and migration backlog

Create a bounded, ordered backlog of implementation work needed after Batch 1. Each item must include:

- exact source and target contract;
- files/functions affected;
- acceptance evidence;
- methodological owner;
- whether Codex can implement mechanically or requires Matías's decision;
- dependency on the other Batch 1 packets.

Avoid generic items such as “refactor notebooks.”

### 9. Improve the smoke distinction without pretending scientific validation

The current smoke test checks structural presence. Preserve that useful distinction.

You may improve its reporting so it clearly labels:

- repository-structure smoke;
- dependency-contract audit;
- scientific execution not performed.

Do not turn the smoke task into a full notebook execution or claim that marker checks validate the poverty methodology.

## Ordered execution

1. Build the notebook/module input-output graph.
2. Inventory all paths and dependencies.
3. Audit legacy names and schemas.
4. Build the expected schema and consumer registry.
5. Classify duplicated versus poverty-specific code.
6. Inventory candidate scientific invariants.
7. Specify one future vertical slice.
8. Produce the adapter/migration backlog.
9. Clarify smoke output and documentation only where evidence supports it.

## Coordination with current authorities

Use these decisions:

- `income-modeling-eph` owns current annual EPH preprocessing and income modeling;
- `encuestador-de-hogares` is legacy lineage evidence;
- `microdatos-EPH-INDEC` owns source acquisition;
- `eph-censo-aligner` owns its mapping release;
- geography producers own geography releases;
- price/basket producers own their versioned artifacts;
- this repository owns poverty-specific integration and research outputs.

When current producer contracts are not yet available, use explicit provisional artifact IDs and record the missing seam.

## Human checkpoints

Stop for review before:

- changing poverty or indigence definitions;
- selecting a basket or price methodology;
- changing household/person aggregation;
- changing sampling or weighting;
- choosing a geography or period for the future release;
- accepting a model output as scientifically adequate;
- deleting notebooks or historical outputs;
- running the full pipeline or publishing results.

## Non-goals

- No full notebook-to-package rewrite.
- No model training or preprocessing duplication.
- No live data refresh.
- No price/basket methodological repair.
- No current poverty estimate.
- No Atlas deployment or Mapbox upload.
- No large data/output commit.
- No scientific claims based on the current structural smoke test.
- No edits to upstream repositories from this branch.

## Stop conditions

Stop rather than guess when:

- a path points to unavailable external/local data;
- an expected column's meaning or unit is unclear;
- income and threshold monetary references cannot be reconciled;
- a legacy model or preprocessing artifact cannot be identified;
- a notebook mixes exploration and production in a way that requires methodological selection;
- a proposed vertical slice would imply a new public result without approval.

## Acceptance criteria

```text
the actual notebook/module pipeline and all write/read paths are mapped
consumer dependencies have proposed producer artifact identities and expected schemas
legacy EPHARG_train and current annual-input assumptions are located and classified
poverty-specific logic is separated from duplicated preprocessing/model/geography logic
candidate scientific invariants are inventoried with evidence status
one bounded future vertical slice is fully specified but not executed
a concrete adapter/migration backlog prepares Batch 2
smoke checks are not misrepresented as scientific validation
no full run, data refresh, model training, publication, or large artifact mutation occurs
```

## Completion report

The final response and PR description must state:

- notebooks, modules, paths, and dependencies inspected;
- unavailable or broken inputs;
- legacy/current compatibility findings;
- code-disposition counts and major conclusions;
- scientific invariants requiring approval;
- the proposed Batch 2 vertical slice;
- exact commands run;
- confirmation that no full poverty computation, model training, data refresh, deployment, or publication occurred.
