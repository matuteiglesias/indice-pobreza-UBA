# Poverty ecosystem current state

As of 2026-09-27.

This document is a **current-state index**, not a new scientific authority. It exists so
future agents do not infer today's work queue from dated runbooks, experiment notes, or
historical commissioning folders.

Authoritative machine-readable scientific status remains:

```text
science/commissioning/registry.json
```

Release semantics remain owned by the release manifests/contracts in their producer
repositories.

## Current scientific spine

| Surface | Current state | Scope / interpretation |
|---|---|---|
| Telescope A | `closed_pass` | observed EPH poverty truth, 2022-Q1..2025-Q4 |
| Telescope B | `closed_pass` | within-EPH observed → OOF point → predictive bridge, Q3 anchor |
| Telescope C | `diagnostic_only` | EPH→Census transport decomposition, Q3 anchor; no Census outcome authority |
| L1 | `closed_pass` | EPH labor truth / official benchmark reproduction, 16 quarters |
| D-1 | `diagnostic_only` | corrected Q3/CPV-2010 source-separation diagnostic; no transport weighting |
| L2 | `closed_pass` | corrected shared-feature labor reconstruction; unresolved H06 excluded |
| L3 | `closed_pass` | exact corrected L2 → 32-domain labor marginal calibration |
| L4 | `closed_negative` | true labor helps welfare; transportable labor probabilities do not |

The Q3 commissioning family is therefore **closed**. It is not a recurring pipeline.
A surface reruns only when its explicit `rerun_trigger` fires.

## What the labor closure means

The three-arm L4 result separates two claims:

```text
labor contains welfare-relevant information          YES
current transportable labor bridge improves welfare  NO
```

L3's near-exact marginal calibration does not change that conclusion. Matching activity
and unemployment margins is a constraint on aggregates; it is not evidence that the
welfare-relevant micro-assignment has been recovered.

The current action is therefore to keep the labor surface available for labor analysis
and diagnostics, but **not** add the commissioned labor probabilities to the welfare
feature set.

## Temporal coverage

The code/contract surface now supports a 2022-Q1..2025-Q4 logical envelope where the
required governed parents exist.

Important distinction:

- Telescope A and L1 already have 16-quarter governed evidence.
- sampler target-year code accepts 2022–2025 under the same CPV-2010 donor-frame design.
- Poverty batch/config plumbing accepts the 16-quarter envelope.
- this does **not** mean every predictive parent/release has been materialized for every
  2022/23 quarter.

Use `docs/CODEX_BACKFILL_2022_2023_VERTICALS.md` as a bounded local-data
materialization runbook, not as evidence that every cell is already present.

## Census donor / semantic state

### CPV-2010

This remains the currently commissioned donor frame for the active poverty surfaces.

The sampler keeps:

```text
selection_probability
!= design_inverse_probability_weight
!= downstream analysis_weight
```

Current target-year poverty releases use their declared analysis-weight semantics; Census
design IPW is not silently promoted into Poverty analysis weights.

### CPV-2022

The architecture is vintage-neutral. Upstream real VP extraction and a
`research.census-frame/v1` adapter have been qualified on bounded real slices.

Still open:

- independent sampler-side bounded real-frame check/sample handoff;
- eventual national frame materialization from the preferred corrected source;
- CPV-2022-specific semantic review in `eph-censo-aligner`;
- downstream donor-vintage sensitivity/adjudication.

This is a donor-frame experiment, not a sampler redesign.

### Semantic plane

`eph-censo-aligner` has a source-backed real policy for EPH 2024-Q3 ↔ CPV-2010.
The commissioned plane has zero hard semantic violations; support-only differences remain
diagnostic. Semantic alignment does not authorize statistical transport.

## Poverty release permissions

`poverty-estimate-release/v2` now emits
`poverty-estimate-capabilities/v2`.

The current capability boundary explicitly separates:

```text
estimate exists
!= estimand represented
!= downstream operation authorized
```

Current governed research releases authorize point **proportions** under their declared
design/analysis-weight semantics.

They do not currently authorize:

- population counts;
- uncertainty intervals;
- inferential rankings;
- significance claims.

Temporal comparison is at most `descriptive_only` unless a future release explicitly
upgrades that permission.

`not_for_interpretation=true` maps to `commissioning_only` presentation.

## Atlas state

The Atlas remains a terminal consumer. It does not calculate poverty, derive new counts,
manufacture uncertainty, or infer publication permissions.

Map/geometry infrastructure is commissioned:

- province Mapbox transport: 24/24 governed IDs;
- department transport: 525/525 governed IDs at the identity gate;
- browser exact-ID runtime and public-token proof: complete.

The new Atlas ingest requires capability v2 and preserves upstream permissions into static
metadata. Browser presentation is deny-by-default.

The currently checked-in older static projections predate the permission object; they
therefore enter `legacy_fail_closed → commissioning` presentation instead of regaining
public-statistic authority by accident.

A future re-projection from current capability-v2 Poverty bundles may change that source
from `legacy_fail_closed` to `declared`, but ordinary public presentation still requires
the upstream release itself to authorize `research_public`.

## Open system questions outside closed commissioning

These are different scientific/product questions and should not be conflated with the
closed Q3 commissioning family:

1. real CPV-2022 donor-frame sensitivity;
2. aggregate/small-area uncertainty design after an estimand is fixed;
3. explicit universe/population-total authority where counts are ever desired;
4. period-comparability commissioning before stronger longitudinal claims;
5. publication approval: when a research release may move from
   `commissioning_only` to `research_public`.

## Status-bearing documentation rule

When documents disagree, use this precedence:

```text
exact release manifest / contract
        ↓
science/commissioning/registry.json
        ↓
this CURRENT_STATE.md
        ↓
README / SYSTEM boundary docs
        ↓
dated runbooks, experiment notes, historical snapshots
```

Historical documents should be preserved and labeled, not rewritten to pretend they were
always current.
