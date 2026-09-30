# Consolidated commissioning framework

This document is the cross-ecosystem map for scientific commissioning.

It does **not** replace Telescope A/B/C, the labor bridge, the semantic plane, or
the poverty estimator. Those surfaces keep their existing ownership and
contracts. This layer answers a narrower governance question:

> Which scientific question is each surface allowed to answer, what evidence
> closes it, and what may consume that answer?

The machine-readable authority is `registry.json`.

## One spine, different questions

The ecosystem uses one commissioning spine:

```text
truth
  ↓
within-domain model
  ↓
transport
  ↓
explicit mechanism-specific calibration
  ↓
downstream-impact adjudication
  ↓
production decision outside commissioning
```

Not every family occupies every stage.

### Poverty

```text
Telescope A
observed EPH poverty truth
        ↓
Telescope B
same-household observed → OOF point → predictive
        ↓
Telescope C
EPH → Census transport decomposition
```

### Historical bounded labor bridge — 2024-Q3

The registry IDs below are retained for the closed 2024-Q3 bridge and must not be reused as shorthand for the newer longitudinal programme.

```text
L1
EPH labor truth / official benchmark reproduction
        ↓
L2
transportable labor probability reconstruction
        ↓
L3
bounded agglomerate marginal calibration
        ↓
L4
does the bridge improve welfare prediction?
```


### Longitudinal welfare/labor — 2017-Q1..2026-Q1

The newer programme is a separate registry surface, `LONG-WELFARE`, owned by
`encuestador-de-hogares`:

```text
L1/L1B official aggregate labor context
          +
L2 real 37-quarter EPH evidence
          +
L3B governed P0_LONG / P1R_NOLAB_LONG composition
          ↓
L10 composition + aggregate labor + explicit time
          ↓
short-gap panel evidence
     ↙             ↘
   L11             L12
stale observed   donor-informed current-state probabilities
     \             /
          ↓
     arm adjudication
          ↓
 bounded Census research scoring
```

This programme is currently `blocked` only at real-scale execution: the first L10 run exhausted practical memory before emitting a result bundle. No longitudinal L10/L11/L12 conclusion exists yet. The historical 2024-Q3 `closed_negative` labor-bridge result is anchor evidence, not a substitute for this adjudication.

### Transport support

```text
D-1
EPH vs Census source separation within governed EPH agglomerates
```

D-1 is shared evidence for transport risk. It does not create weights or
authorize a new transport model.

## What "commissioned" means

Commissioning is question-specific. A surface does not receive a generic badge
that propagates authority downstream.

The controlled current states are:

- `closed_pass`: the declared question is answered for the declared scope;
- `closed_negative`: the declared hypothesis failed and should not receive
  further tuning without a material upstream change;
- `diagnostic_only`: valid evidence that cannot authorize production;
- `revalidate`: one bounded rerun is required because a governed upstream
  contract changed;
- `blocked`: a required governed parent is absent;
- `superseded`: retained only as historical/regression evidence.

A closed surface is reopened only by its explicit `rerun_trigger` in the
registry.

## Calibration is not one generic operation

The repository must never grow a generic "calibrate Census until it looks like
EPH" layer.

Current mechanisms are deliberately separate:

| mechanism | role | allowed target |
|---|---|---|
| PONDIH | observed poverty measurement | Telescope-A EPH household/population estimand |
| PONDERA | official labor/population composition | L1 truth and L3 target construction |
| unit rows | model support | estimator-facing EPH/Census support comparisons |
| nested outer-fold residual ECDF | predictive welfare distribution | Telescope B/C only, leakage-safe |
| two logit offsets | Census labor marginals | L3 activity and unemployment|active only |
| Census design inverse probability | sampling/design audit | **never an analysis weight** |

No mechanism above implies permission to use another.

## Promotion gates

### Telescope A

May establish observed poverty truth for a governed EPH cohort.

It cannot authorize a predictive model.

### Telescope B

May establish where the welfare model loses information and whether the nested
predictive distribution improves threshold behavior.

It cannot authorize Census transport.

### Telescope C

May quantify EPH→Census point/predictive transport.

It remains diagnostic while Census lacks welfare outcome authority.

### L1

May establish labor truth and calibration targets.

### L2

May establish OOF reconstructability of labor state from transportable
covariates.

A good labor classifier does not imply welfare value.

### L3

May force the declared labor marginals to the L1 targets inside the governed EPH
frame.

Passing L3 does not imply correct within-domain micro-assignment.

### L4

Is the only labor gate that can justify labor-bridge probabilities as welfare
features.

The relevant comparison is always:

```text
no labor
true-labor oracle
OOF transportable labor probabilities
```

The corrected Q3 rerun confirmed the prior result: true labor improves welfare
prediction, while the transportable labor probabilities do not recover that
gain. L4 is therefore `closed_negative`. Do not restart feature engineering
without an explicit upstream invalidation trigger.

### D-1

May establish source separation and identify which semantic role blocks add
transport signal.

It must not generate IPF/raking or density-ratio weights.

## Current consolidation decisions

The registry intentionally prunes three wedges from the active surface:

1. the old Q8 global in-sample EPH/Census classifier is historical regression
   evidence; D-1 is the active source-separation diagnostic;
2. the September Q4 labor reconstruction is a prior; L2/L4 are the active labor
   reconstruction/downstream-impact authority;
3. `ajustar_empleo` is frozen for reproducibility only; L1/L2/L3 own current
   labor truth/reconstruction/calibration.

The large joint-distribution program is not active work. Pairwise matrices,
joint-cell cubes, density-ratio weighting, IPF/raking and a general transport
subsystem require a new scientific question and explicit authorization.

## Q3 closure result

The bounded 2024-Q3 closure packet is complete and validated:

- **D-1:** `diagnostic_only`; the corrected marginal refresh preserves the
  source-separation interpretation (stable/shared near-random; target-period
  and research-only tiers add separation).
- **L2:** `closed_pass`; the corrected feature contract excludes unresolved
  `H06` and the grouped-OOF labor reconstruction remains coherent.
- **L3:** `closed_pass`; the exact corrected L2 artifact feeds 32 calibrated
  EPH-frame domains, with the outside-frame domain retained as unbenchmarked.
- **L4:** `closed_negative`; the true-labor oracle materially improves welfare,
  while the transportable labor bridge is neutral/slightly harmful.

The scientific conclusion is intentionally bounded: labor contains
welfare-relevant information, but the currently transportable reconstruction
does not preserve enough of that information to be a useful welfare feature.

There is no automatic expansion of the closed 2024-Q3 commissioning family. Closed questions rerun only on their explicit registry triggers. The active longitudinal work is separately represented by `LONG-WELFARE`, whose next step is resource-safe execution rather than a new labor estimator. D-2, L5, Telescope D, generic raking/IPF, density-ratio weighting and a joint-distribution program are not implied next steps.

## Mechanical Q3 closure packet

The accepted closure receipt is preserved under `science/commissioning/receipts/` for durable audit. The registry remains the status authority; the receipt is evidence, not a second queue.

The bounded Q3 revalidation is complete. The following machinery is retained
for audit/reproduction and for future trigger-driven revalidation, not as a
standing work queue.

The closure is governed by the registry program
`2024-Q3-commissioning-closure-v1`. It covers only `D-1`, `L2`, `L3` and
`L4`.

Create a deterministic empty receipt before the local real-data run:

```bash
python science/commissioning/registry.py \
  --init-closure 2024-Q3-commissioning-closure-v1 \
  --output /home/matias/data/COMMISSIONING_CLOSURE_2024Q3.json
```

The local run fills exact producer commits, artifact identities, parent identities,
evidence identities and the existing experiment-specific acceptance result. The
registry validator deliberately does **not** infer scientific success from a new
metric threshold.

Validate and render the completed receipt with:

```bash
python science/commissioning/registry.py \
  --validate-closure /home/matias/data/COMMISSIONING_CLOSURE_2024Q3.json

python science/commissioning/registry.py \
  --render-closure /home/matias/data/COMMISSIONING_CLOSURE_2024Q3.json
```

Structural closure fails closed when:

- a terminal question lacks exact producer/artifact/evidence identity;
- evidence or parents come from the wrong period;
- a dependency is still `revalidate` / `blocked`;
- L3 does not consume the exact L2 artifact declared in the same packet;
- the corrected L2 feature contract still contains `H06`;
- the L3 packet does not retain the governed 32-domain gate;
- the three L4 arms differ in row universe, folds, welfare target, scoring,
  model family or non-labor feature contract.

For L4, `closed_negative` is permitted only after the receipt explicitly
records the governed adjudication that oracle labor is useful and the
transportable bridge does not improve the welfare result. The validator checks
that declaration; it does not manufacture it from metrics.

Hosted CI exercises only synthetic closure receipts. Real Census/EPH evidence
remains local and is never fabricated by CI.

Once a question reaches a terminal state, it is **not a recurring pipeline
stage**. It reruns only after the explicit upstream invalidation trigger already
recorded in the registry.

## Registry check

```bash
python science/commissioning/registry.py
python science/commissioning/registry.py --summary
```

The validator checks controlled statuses, explicit authorities, non-dangling
dependencies, acyclicity and the cross-ecosystem weight/calibration invariants.
It validates governance structure only; it does not pretend to recompute local
real-data evidence in hosted CI.
