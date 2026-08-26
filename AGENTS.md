# Agent contract — Poverty Estimation v2

This repository is the terminal scientific authority for project-specific poverty measurement and estimation. It is not the place where upstream data/model/geography work is reconstructed.

## Read first

Before changing production code, read:

1. `docs/ARCHITECTURE_V2.md`
2. `docs/DEVELOPMENT_PROGRAM_V2.md`
3. `docs/UPSTREAM_HANDOFFS_V2.md`
4. `SYSTEM.yaml`
5. the current implementation and tests relevant to the bounded wave.

Always start each wave from fresh current `main` and re-check exact upstream contracts/releases rather than trusting an earlier branch or conversation.

## Scientific ownership

This repository may own:

- the versioned poverty method used by this project;
- adult-equivalence application as part of that method;
- household poverty/indigence thresholds and classifications;
- FGT poverty estimands and related poverty diagnostics;
- aggregation/estimation semantics from already-governed micro estimates or classifications;
- propagation of uncertainty supplied by upstream welfare/frame artifacts;
- parity/calibration checks that evaluate the poverty measurement itself;
- immutable poverty estimate releases, QA and limitations.

It does not own:

- Census acquisition, sampling, geography construction or projection-model invention;
- EPH acquisition or official EPH geography;
- income-model training, model selection or Census scoring orchestration;
- conversion of research-model outputs into deployable welfare estimates;
- Argentine geography or Census↔EPH/electoral relations;
- basket source acquisition/price-index production;
- maps, web publication, electoral enrichment, employment series or nowcasting.

## Core invariant

The active poverty runtime begins only after it receives compatible, immutable representations of:

1. a population/frame sample;
2. welfare estimates in an approved linear monetary concept;
3. a versioned poverty method;
4. poverty lines for the requested period/threshold area.

If an upstream model used logs, ensembles, calibration, smearing, simulation or other transformations, those details belong in upstream lineage. The poverty measurement kernel must not recreate model inference or guess a retransformation.

## Temporal invariant

Never equate these concepts implicitly:

- `frame_vintage`;
- `welfare_period`;
- `poverty_line_period`;
- `estimation_period`;
- model training window.

Compatibility must be explicit. CPV-2010 may serve as a frame for a later research estimate without being relabeled as a later Census.

## Geography invariant

The scientific kernel consumes geographic IDs as grouping/domain keys only. It must not load shapefiles, perform spatial joins, choose a geography provider or construct poverty-region mappings. Geometry belongs to `argentina-geography` and publication consumers.

## Method invariant

Method ambiguity is resolved into a versioned poverty-method contract; it does not become an unbounded configuration surface. Equality semantics, adult-equivalence rules, welfare concept, person inheritance and poverty-gap definitions must be named and testable.

## Uncertainty invariant

Do not manufacture uncertainty downstream. The poverty layer may propagate model draws, replicate weights or other uncertainty representations supplied under an explicit upstream contract. If only point estimates exist, report point estimates and the limitation rather than inventing standard errors.

## Development discipline

- Keep PRs bounded to one wave/capability.
- Prefer small semantic commits.
- Preserve historical notebooks/data as evidence until an explicit decommission wave.
- New v2 contracts may coexist with v1 while migration is proven.
- Do not delete v1 functionality merely because a target v2 architecture exists.
- Fail closed on identity, monetary-reference or method incompatibility.
- QA warnings may pass when scientifically bounded and explicitly surfaced.
- Never label project outputs as official INDEC poverty statistics.

## Stop conditions

Stop the specific scientific decision rather than guessing when:

- the welfare concept or monetary reference is ambiguous;
- a poverty-line source cannot be pinned;
- Census/frame weighting semantics are unclear;
- adult-equivalence semantics differ materially from the approved method;
- a requested uncertainty statistic cannot be justified by supplied uncertainty inputs;
- a change would silently alter previously published poverty classifications or estimands.

Continue all independent mechanical/documentation work that remains safe.
