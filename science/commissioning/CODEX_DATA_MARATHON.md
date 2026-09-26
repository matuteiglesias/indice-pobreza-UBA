# Codex marathon — materialize the commissioning data backbone

This document defines bounded local-agent missions that feed
\`science/commissioning/\` without changing poverty/model semantics.

Run missions independently when their parents exist. Each mission must:
- preserve existing scientific contracts;
- write local artifacts only;
- report exact parent identities and counts;
- stop on contract failure rather than silently intersecting/coercing;
- update PR #35 only for narrow adapter/render integration fixes.

## Mission A — 8-quarter EPH labor reality surface

Goal: fill Figure 5 completely for 2024-Q1..2025-Q4.

Inputs: governed raw EPH person releases for all eight quarters.

For each quarter, provide the exact raw person file path in the commissioning config under
\`parents.eph_person_files\`.

Required local validation for each quarter:
- parse \`ESTADO\` and \`PONDERA\`;
- no negative weights;
- report weighted employed / unemployed / inactive person stocks;
- report activity, employment and unemployment rates;
- compare against the pinned official benchmark rates in
  \`science/commissioning/benchmarks/indec_labor_quarter.csv\`;
- report rate deltas in percentage points.

Do not calibrate or alter weights.

Deliverable: one config patch/path map covering all 8 quarters plus a table of
official vs reconstructed rates and stocks.

## Mission B — Telescope A for all 8 quarters

Goal: create the observed-reality temporal backbone for Figures 1, 4, 6 and 7.

Periods:
\`2024-Q1\` through \`2025-Q4\`.

For each quarter, run the existing Telescope-A method with the same commissioned semantics:
- positive-PONDIH income-support cohort;
- observed ITF welfare;
- canonical adult equivalents and regional nominal lines;
- PONDIH weighting;
- exact person inheritance of household poverty state;
- no ML and no Census.

Output directories should follow:
\`/home/matias/data/telescope-a-<period-lower>\`

Each must contain at least:
- \`households.parquet\`
- \`summary.json\`
- existing Telescope-A report/QA outputs.

Acceptance per quarter:
- raw period identity exact;
- no silent cohort intersection;
- ITF/P47T reconciliation reported;
- six regional estimates present;
- national person poverty/indigence present;
- household state columns retained for age grouping.

After completion, add all eight Telescope-A paths to the commissioning config and rerun
PR #35. Figures 1, 4, 6 and 7 should become genuine time-series/cross-period views.

Do not modify Telescope-A science merely to harmonize quarters.

## Mission C — Telescope B anchor-quarter panel

Goal: determine whether Q3 point compression / residual behavior persists through time.

Start with four anchors:
- 2024-Q1
- 2024-Q3
- 2025-Q1
- 2025-Q3

Only expand to all 8 after the anchor panel is scientifically coherent.

For each anchor:
- consume that quarter's exact Telescope-A household cohort;
- use the quarter-matched governed P1-R OOF predictions;
- use the quarter-matched nested outer-fold residual ECDFs;
- preserve exact same-household identity;
- produce the existing Telescope-B outputs including \`bridge.csv\` and
  \`households.parquet\`.

Acceptance:
- exact Telescope-A cohort preserved;
- OOF person coverage exact;
- one outer fold per household;
- fold-specific residual ECDF only;
- no global residual substitution;
- observed / OOF point / predictive I-PNI-N reconcile;
- flow identities pass.

Report for persons, each quarter:
- observed poverty / indigence;
- OOF point poverty / indigence;
- predictive poverty / indigence;
- point-model deficit;
- residual correction.

Then add those Telescope-B directories to the commissioning config.

## Mission D — Telescope C anchor-quarter transport panel

Goal: test whether the Q3 EPH->Census point-transport effect persists.

Prerequisite: corresponding Telescope-B anchor quarter must be commissioned.

Start with:
- 2024-Q1
- 2024-Q3
- 2025-Q1
- 2025-Q3

For each quarter:
- reuse exact matched outer models \`M_-f\`;
- reuse exact nested residual ECDFs \`G_-f\`;
- score the governed Census-derived target-year semantic sample;
- preserve the Telescope-C point/predictive transport decomposition.

Do not condition residuals or introduce production transport weights.

Required report:
- EPH point/predictive poverty + indigence;
- Census point/predictive poverty + indigence;
- point transport;
- predictive transport;
- transport x residual interaction;
- any model-reproduction warning, with affected row count and magnitude.

If quarter-specific model reproduction fails materially, stop that quarter instead of
forcing comparability.

Then add successful Telescope-C directories to the commissioning config.

## Mission E — department-release panel

Goal: unlock Figure 10 once the department layer is commissioned.

Use only verified \`poverty-estimate-release/v2\` outputs with
\`geography_level=department_2010\`.

Preferred target: all 8 quarters.

Acceptance per quarter:
- governed 525 department IDs;
- no duplicate department poverty FGT0 rows;
- person weighted denominator positive;
- department -> province -> national reconciliation passes;
- no fuzzy/name joins.

Add release directories to \`parents.poverty_releases\`.

Figure 10 then consumes only released person-poverty FGT0 and released denominators to
show weighted department-distribution quantiles.

## Final integration pass

After each mission, rerun:

\`\`\`bash
PYTHONPATH=src python science/commissioning/run.py \
  --config <local-config.json> \
  --output /home/matias/data/poverty-commissioning-expanded
\`\`\`

Inspect every PNG, not just file existence.

Expected maturity sequence:
1. A -> Figure 5 full 8-quarter labor panel.
2. B -> Figures 1/4/6/7 gain real temporal structure.
3. C -> Figure 8 becomes a model-behavior time panel.
4. D -> Figure 9 becomes a transport time panel.
5. E -> Figure 10 unlocks.

Large generated artifacts remain local. Do not merge PR #35 until the real-data
renderers and adapters have been exercised and reviewed.
