# Poverty ecosystem baseline — 2026-09-30

Status: cross-repository coordination baseline after the Sep-29/Sep-30 longitudinal labor sprint.

This document summarizes already-governed producer state. It is not a new estimator and
does not override exact release manifests/contracts. Use it to prevent future work from
reopening settled ownership and clock decisions casually.

## Authority map

| Surface | Authority | Current role |
|---|---|---|
| official EPH microdata custody | `microdatos-EPH-INDEC` | immutable quarterly EPH source parents |
| official aggregate labor context | `empleoARG` | INDEC activity/employment/unemployment/subemployment by quarter/geography |
| EPH preprocessing / longitudinal analysis frame | `income-modeling-eph` | source-backed 37-quarter EPH evidence and repeated-wave audit |
| EPH↔Census semantics / canonical composition | `eph-censo-aligner` | named profiles, semantic recodes, explicit donor clocks |
| Census sampling / target population | `samplerCensoARG` | exact Census sample identity and canonical department target mass |
| monetary references / conversion | `IPC-Argentina` | immutable candidate/approved monetary conversion authority |
| CBA/CBT / Engel threshold research | `canastasINDEC` | governed basket inputs and threshold sensitivities |
| survey→Census welfare transport | `encuestador-de-hogares` | L10/L11/L12 transport/welfare science and scoring |
| poverty method / FGT | `indice-pobreza-UBA` | terminal poverty measurement/estimation and cross-ecosystem commissioning |
| public presentation | `argentina-poverty-atlas` | terminal permission-preserving consumer |

## Two labor programmes — do not conflate them

The commissioning registry retains a bounded **2024-Q3 labor bridge** with historical
surface IDs `L1/L2/L3/L4`. That programme is closed for its declared scope:

- true current labor contains welfare signal;
- its commissioned transportable labor-probability bridge did not improve matched welfare;
- the result remains useful anchor evidence.

A newer, separate **2017-Q1..2026-Q1 longitudinal welfare programme** is registered as
`LONG-WELFARE`. It changes the question and the information architecture:

- L10 = canonical composition + observed aggregate labor context + explicit time;
- L11 = L10 + genuinely earlier observed EPH labor state on supported repeated-wave gaps;
- L12 = L10 + OOF donor/stale-informed probabilities of current labor state, with optional governed anchoring.

The historical Q3 negative bridge result does not adjudicate this newer programme.

## Frozen longitudinal baseline

Treat the following as settled unless new evidence specifically breaks a contract:

1. observed EPH longitudinal measurement window is `2017-Q1..2026-Q1`;
2. current aggregate labor authority is `empleoARG`; source observations and completion overlays are distinct artifacts;
3. canonical composition authority is `eph-censo-aligner`;
4. `P1R_NOLAB_LONG` is the richer centerline composition candidate; `P0_LONG` is the matched baseline;
5. L10 excludes current person `CONDACT`;
6. donor labor always carries an explicit observation clock/vintage;
7. repeated EPH evidence supports short-gap labor research, not CPV-2010→current identification;
8. explicit time effects are fitted from nested household-safe OOF base predictions;
9. 2020-Q2 and 2024-Q1/Q2 remain measured but do not estimate ordinary year/quarter structure;
10. KL projection is an L12-only sensitivity under a proven compatible universe;
11. longitudinal execution is measurement-mode, not forecast/nowcast;
12. reviewed historical survey-special values may become feature-level canonical nulls without dropping C2 rows.

## Materialized longitudinal parents

### L1 / L1B — aggregate labor

Official release:

`indec-eph-labor-state-52ca6bcb586f2b0b`

Coverage is 1,060/1,064 required official cells. The only required gap is NEA 2019-Q3
across the four principal indicators.

Derived model-context overlays remain separate:

- `indec-eph-labor-context-completion-backward_fill-2212ec7a74aa7f16` — centerline;
- `indec-eph-labor-context-completion-forward_fill-71229ee29569dc24` — sensitivity.

### L2 — longitudinal EPH

`eph-longitudinal-2017q1-2026q1-c155bb8f847a2f39`

- 37/37 exact quarterly parents;
- 1,869,620 person-period rows;
- zero-income observations retained;
- repeated-wave candidate audit persisted;
- midpoint quarter timing is the bounded-commissioning monetary centerline;
- the monetary conversion parent remains candidate, so approved-mode scientific freeze is not yet claimed.

### L3A — donor labor

`eph-cpv2010-semantic-plane-2024q3-v2`

- 469,172 CPV-2010 donor persons;
- donor labor clock is explicitly 2010;
- no target-period current-state or transport-validity claim.

### L3B — canonical composition

- `P0_LONG`: `eph-longitudinal-composition-p0_long-7b8fdc0ec1f2a553`;
- `P1R_NOLAB_LONG`: `eph-longitudinal-composition-p1r_nolab_long-ed30aa112c9b7d31`.

Both preserve all 1,869,620 C2 rows over 37 periods. Recognized historical special
states are governed feature-level nulls; unresolved substantive codes still fail closed.

## Measurement / threshold baseline

The Sep-28 measurement-alignment package is real-data materialized:

- `measurement-alignment-9881018e3eaef09f` covers 16 quarters, 2022-Q1..2025-Q4;
- Telescope-A baseline reproduction passes;
- M1 timing and M3 signed-sales Engel sensitivities are diagnostic rather than new welfare estimators.

CEDLAS forensic evidence is also published:

- threshold: `cedlas-dt370-replication-2eedcb977b47232e`;
- poverty replication: `cedlas-poverty-replication-a301021eaaf80dde`;
- paper-exact Table-5 reproduction is within the declared 0.1 pp tolerance;
- choice attribution separates reference population, food scope and regionalization effects without claiming additivity.

## Census population / donor baseline

`samplerCensoARG` now owns a real-source-validated canonical department population
producer for 2001–2035:

- legacy levels retained through 2010;
- explicit derived bridge for 2011–2021;
- INDEC Census-2022-based estimates used from 2022;
- period-native geography and explicit seam/alignment diagnostics retained.

CPV-2010 remains the currently commissioned donor for the active scoring research.
CPV-2022 still requires its own national materialization/semantic review before promotion.

## Current development frontier

All data/semantic prerequisites for longitudinal L4 Gate A are green.

The first real L10 execution failed **before emitting a result bundle** because the current
runtime materializes the full 1.87M-row EPH and composition surfaces as Python object-heavy
lists and exhausted practical RAM/swap.

Therefore:

```text
LONG-WELFARE status = blocked
blocker = resource-safe execution plane
scientific L10/L11/L12 result = not yet produced
```

The next implementation frontier is C6-style execution hardening: compact columnar
representation, bounded/sequential fold execution and restartable checkpoints while
preserving the already-reviewed C4B fold/time/composition semantics.

Do not treat this resource blocker as a reason to reopen L1/L2/L3 semantic architecture.

## Status precedence

When summaries disagree:

```text
exact release manifest / contract
        ↓
science/commissioning/registry.json
        ↓
docs/CURRENT_STATE.md
        ↓
this dated ecosystem baseline / repo README / SYSTEM
        ↓
dated runbooks and historical experiment notes
```
