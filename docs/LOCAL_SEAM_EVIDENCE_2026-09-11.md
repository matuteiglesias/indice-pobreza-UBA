# Local seam evidence — 2026-09-11

This note records the exact local evidence used to wire the first real sampler → predictive welfare → poverty integration acceptance run.

## Exact identities

- Census sample release: `census-sample-2024-0839713eafea8d1b`
- Sample manifest SHA-256: `28691fb0fe71fd6f24648b672413849e905f7ce829eba003dc36881a4c70ab72`
- Semantic release: `eph-cpv2010-semantic-plane-2024q3-v1`
- Semantic manifest SHA-256: `8468f35149a98e59d2614dd8bbb892cd5a68d27c7f88419deb250f5ea89fce26`
- EPH release: `eph-2024-q3-3b6a7a15c4af`
- Census persons: 469,172
- Census households: 141,863

Exact set equality was locally verified for semantic `row_id` versus sampler `sample_person_id`, semantic `household_id` versus sampler `sample_household_id`, and Q8 household IDs versus sampler household IDs. No unmatched or duplicate IDs were found.

## Demographic/geography seam

Sampler v2 carries `department_id`, `radio_id`, `selection_probability`, and complete household membership. Census person payload has `P02` and `P03`; approved mappings are `P02: 1=male, 2=female` and `P03: completed age in years`.

Province is not explicit in the sampler payload. The first acceptance run uses the existing governed `data/info/DPTO_PROV_Region.csv` department-to-basket-region binding rather than inventing a new geography rule.

## Basket / monetary seam

The locally available Q3 basket candidate is:

`/home/matias/repos/old/canastasINDEC/data/CB_Reg_defl_Q.csv`

SHA-256: `114efe353c98bd875bfef882d13a636df32ab92c930c985fe967062d6d0cb002`

It contains all six regions for `2024-08-15` (2024-Q3) on a 2016-01 reference scale.

The governed quarterly IPC evidence gives:

- 2024-Q3 index: `8700.216227330187`
- 2016-01 reference index: `100.0`
- scalar nominal-Q3 → 2016-01 reference: `0.011493967206201482`

The same positive scalar must be applied to point welfare and residuals.

## EPH region coverage

The approved EPH `REGION` mapping covers all 12,568 complete validation households:

- 1 → Gran Buenos Aires
- 40 → Noroeste
- 41 → Noreste
- 42 → Cuyo
- 43 → Pampeana
- 44 → Patagónica

Unmatched households: 0.

## Direct observed EPH reference

Unweighted direct observed household P47T, with real household-specific adult-equivalent regional CBA/CBT lines, produced:

| Concept | FGT0 | FGT1 | FGT2 |
| --- | ---: | ---: | ---: |
| Indigence / CBA | 0.074714 | 0.025702 | 0.014553 |
| Poverty / CBT | 0.307209 | 0.114603 | 0.060334 |

These are a research acceptance reference, not official poverty estimates.

## Explicit limitations

- Collective/private dwelling refinement is deferred for this pass.
- The current local Q3 basket file is usable but is not yet a clean immutable v2 integration release.
- The acceptance estimator uses explicit unit weights; sampler inverse selection probability remains design/audit metadata only.
- Aggregate uncertainty is not supplied.
- Q8 transport caveats remain active.
