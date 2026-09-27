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

### Labor

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

If the bridge again fails to recover a material fraction of the oracle gain
after the current bounded revalidation, close it negative rather than starting
a feature-engineering program.

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

## Near-term closure queue

There are only three bounded reruns in the active registry:

1. **D-1 marginal refresh** after categorical canonicalization/missingness
   reporting. Existing OOF source-classifier conclusions remain valid.
2. **L2/L3** once after removal of unresolved H06 from the governed labor bridge
   feature contract.
3. **L4** once on that aligned L2/L3 output. If the prior negative welfare result
   is materially unchanged, set L4 to `closed_negative`.

Everything else should be treated as closed or diagnostic for its stated scope,
not as a standing invitation to extend the experiment.

## Mechanical Q3 closure packet

The bounded Q3 revalidation is governed by the registry program
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
