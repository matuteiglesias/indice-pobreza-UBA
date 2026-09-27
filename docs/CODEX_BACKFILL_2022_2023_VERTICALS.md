# Codex mission — backfill 2022–2023 to 2024–2025 parity

Use current `main` in all repositories after the longitudinal plumbing merges.

## Cloud-prepared state

The cloud work has already established:

- `microdatos-EPH-INDEC`: acquisition CLI is year/quarter parameterized; no 2022/23 code fork is needed.
- `income-modeling-eph`: governed annual input/model envelope already includes 2022, 2023, 2024 and 2025. Do not invent a second model path.
- `samplerCensoARG`: governed target-year sampling accepts 2022–2025 using the same CPV-2010 donor frame, target-population source, deterministic score, probabilities and weight semantics.
- `indice-pobreza-UBA`: predictive geography batch accepts chronological periods in 2022-Q1..2025-Q4 and includes a 16-quarter logical batch spec.
- Official INDEC poverty semester and headline labor-quarter benchmarks are committed for 2022–2025.
- EPH agglomerate G1/G2/G3/G5 plumbing is already merged.
- Atlas release-period handling is dynamic; do not add year-specific UI logic.

## Objective

Make 2022 and 2023 first-class verticals matching the existing 2024/25 capability surface wherever current scientific contracts legitimately support them.

Target periods:

```text
2022-Q1 Q2 Q3 Q4
2023-Q1 Q2 Q3 Q4
```

Do not change science merely to fill cells.

## Phase A — capability census first

Inspect real local manifests and create:

```text
/home/matias/data/poverty-2022-2025-capability-matrix.csv
/home/matias/data/poverty-2022-2025-capability-matrix.json
```

Rows must include:

- governed EPH person/household release
- Telescope A
- labor benchmark/reconstruction
- Census target-year sample
- population frame
- predictive welfare
- province release
- department release
- G2 agglomerate sidecar
- G3 observed agglomerate release
- G5 predictive agglomerate release
- Telescope B
- Telescope C
- commissioning dashboard
- Atlas projection

Statuses:

```text
PRESENT
MISSING_PARENT
MISSING_RUN
MISSING_CODE_SUPPORT
SCIENTIFIC_DECISION_REQUIRED
NOT_APPLICABLE
```

Do not proceed blindly until this matrix exists.

## Phase B — acquire and govern EPH 2022/23

For every old quarter use the normal `microdatos-EPH-INDEC` acquisition/publication path.

Hard gates:

- exact requested year/quarter;
- persons + households present;
- ANO4/TRIMESTRE match;
- source manifest/hash recorded;
- no quarter reuse.

Produce a compact acquisition census with row counts and source hashes.

## Phase C — Telescope A and observed reality

Run the exact current Telescope-A path for all eight quarters.

Do not alter:

- ITF/PONDIH universe;
- P47T diagnostic semantics;
- adult-equivalent mapping;
- REGION→basket-region mapping;
- quarter basket aggregation;
- <= threshold convention;
- FGT definitions.

Persist a 16-quarter summary extending the existing 2024/25 spine.

Compare 2022/23 quarter pairs with the committed official semester benchmarks only as a commissioning approximation; do not call the quarter mean the official estimator.

## Phase D — labor reality surface

Reconstruct the same EPH labor headline rates used in 2024/25:

- activity;
- employment;
- unemployment.

Compare exactly against the committed 2022/23 official quarterly benchmarks.

If existing governed raw fields make it straightforward, also emit a separate diagnostic table for:

- occupied job seekers;
- underemployment;
- underemployment demanding;
- underemployment non-demanding.

Do not change production labor treatment or CONDACT in this mission.

## Phase E — Census target-year samples 2022 and 2023

Using `samplerCensoARG` current main:

1. rebuild/materialize the governed department target-population parent covering 2022–2025 from the exact committed INDEC source;
2. build 2022 and 2023 target-year sample releases with the exact current sampling algorithm;
3. use the same fraction/seed/policies as 2024/25;
4. verify household completeness, probability semantics and deterministic common-score behavior.

Report:

- households/persons;
- department coverage;
- target person mass;
- selection probability range;
- design inverse-probability diagnostics;
- exact parent/release hashes.

Do not use design weights as poverty analysis weights.

## Phase F — G1/G2/G3 agglomerates

Reuse:

```text
/home/matias/data/eph-agglomerates-g1
```

Build G2 sidecars for 2022 and 2023 from G1.

Requirements:

- 32 native agglomerates;
- zero household loss;
- outside-EPH-frame rows retained;
- no imputation/redistribution/weight change.

Then build G3 observed releases for all eight 2022/23 quarters.

Each G3 release:

- 396 facts;
- 32 `eph_agglomerate` domains;
- `eph_coverage/EPH_TOTAL`;
- no `national/ARG`;
- exact EPH_TOTAL parity with Telescope A person FGT0 poverty/indigence.

Extend the existing G2 coverage and G3 parity files to 2022–2025.

## Phase G — determine predictive-policy validity before scoring

Audit the exact current predictive-welfare/model manifest lineage.

Important: `income-modeling-eph` already contains a 2022–2025 annual modeling envelope, but the active poverty predictive release has its own lineage and must be authoritative.

Answer explicitly:

1. Is the production predictive model frozen over a 2022–2025 training envelope?
2. Is scoring a 2022 or 2023 Census-target representation allowed by the current contract?
3. Would producing 2022/23 welfare require retraining or changing the feature plane?

If scoring is authorized without scientific change, proceed.

If it requires retraining, a different cohort, different residuals, or an unapproved back-cast assumption, mark the predictive cells `SCIENTIFIC_DECISION_REQUIRED` and stop that predictive branch.

Do not silently retrain merely to obtain complete rows.

## Phase H — predictive releases where valid

For every period whose predictive parents are governed and contract-valid:

- build/locate exact population frame;
- build/locate exact predictive welfare;
- use exact basket parent;
- run province and department releases;
- reconcile department→province;
- build G5 agglomerate release using the year G2 patch and governed agglomerate→poverty-region binding.

Administrative releases retain `national/ARG`.
Agglomerate releases use `eph_coverage/EPH_TOTAL`.

Use the committed logical envelope:

```text
configs/releases/predictive-poverty-2022q1-2025q4.json
```

Create a parent-resolution JSON from the real local manifests. Never guess paths or hashes.

## Phase I — B/C and transport

Mirror the currently governed B/C period policy; do not create extra anchors merely for symmetry.

Where B/C are scientifically valid, materialize them using the canonical household-grouped fold contract and exact B→C fold identity.

For quarters with observed + predictive agglomerate releases, run the existing agglomerate comparator.

Do not overwrite the commissioned 2024-Q3 decomposition.

## Phase J — commissioning dashboard and Atlas

Create a 16-quarter commissioning config from 2022-Q1 through 2025-Q4.

Run capability-driven figures.

Classify every figure:

```text
READY
PARTIAL_PERIOD_COVERAGE
BLOCKED_MISSING_PARENT
BLOCKED_SCIENTIFIC_POLICY
```

Project every valid release family into Atlas.

Run:

```bash
npm test
npm run lint
npm run typecheck
npm run verify
npm run build
```

No year-specific Atlas hack is allowed.

## Required final outputs

At minimum:

```text
/home/matias/data/poverty-2022-2025-capability-matrix.csv
/home/matias/data/telescope-a-2022-2025-summary.csv
/home/matias/data/eph-labor-2022-2025.csv
/home/matias/data/eph-agglomerate-g2-coverage.csv
/home/matias/data/eph-agglomerate-g3-parity.csv
/home/matias/data/poverty-economic-spine-2022-2025.csv
/home/matias/data/poverty-2022-2025-backfill-summary.json
```

Also return:

- real 2022/23 sample release IDs and hashes;
- predictive periods successfully completed;
- periods blocked by scientific policy;
- B/C status;
- Atlas status;
- every bounded code change made locally.

## Scientific non-changes

Do not:

- change Telescope-A;
- change PONDIH semantics;
- change poverty method/baskets;
- change model features;
- change residual calibration;
- retrain just to fill 2022/23;
- change sampler science;
- use design weights as analysis weights;
- infer agglomerates spatially;
- calibrate Census by agglomerate;
- turn on target-period labor reconstruction.

This mission is temporal parity under current production science.
