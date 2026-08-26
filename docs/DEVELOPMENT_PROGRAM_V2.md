# Poverty Estimation v2 — development program

This program guides bounded autonomous work from the current consumer-only v1 runtime toward a thinner, stronger poverty-estimation authority.

Waves are ordered by dependency, not by ambition. A later wave may be split when a source/contract boundary becomes large. A wave may also be skipped if evidence shows that the capability belongs elsewhere.

## P0 — architecture reset

**Mission:** establish the v2 scientific boundary and remove ambiguity about ownership before changing the kernel.

Required:

- mission/non-ownership authority;
- four-input conceptual model;
- separate frame/welfare/line/estimation clocks;
- upstream handoff requirements;
- migration/decommission map;
- explicit statement that geography/publication/model training remain outside the poverty kernel.

Non-goals:

- changing scientific outputs;
- deleting legacy evidence;
- inventing uncertainty;
- modifying sibling repos.

DoD: future agents can decide where a requested feature belongs without reverse-engineering notebooks.

## P1 — poverty-method contract

**Mission:** replace free-floating method switches with one explicit, versioned method definition compatible with the current INDEC line-poverty methodology used by the project.

Required:

- method identity/version;
- official methodology references;
- adult-equivalence rule/table and supported demographic domain;
- household welfare concept expected at the poverty boundary;
- CBA/CBT household-threshold construction;
- poverty/indigence comparison semantics;
- person-inherits-household-status rule;
- canonical FGT contribution definitions;
- machine-readable method fixture/contract;
- tests that reject unknown or internally inconsistent method definitions.

Important methodological distinction:

- INDEC's published incidence language uses households whose income does not exceed the line;
- historical examples often describe income below/inferior to the line.

P1 must document and version the exact implementation choice rather than leave it as a perpetual arbitrary runtime switch. If parity testing later shows a needed correction, that is a method-version change with regression evidence.

Non-goals:

- real poverty-line acquisition;
- estimation weights;
- Census/EPH adapters;
- official parity execution.

DoD: a pure kernel can receive a `PovertyMethod` object and no longer needs independent equality/gap policy knobs.

## P2 — pure FGT measurement kernel

**Mission:** create a small, dependency-free scientific kernel for household and person poverty contributions.

Inputs:

- persons with household membership and demographics;
- household welfare in approved linear units;
- adult-equivalence method;
- poverty line(s) per adult equivalent already resolved for each household/domain;
- explicit method object.

Required outputs per household:

- adult-equivalent units;
- household CBA/CBT thresholds;
- poor/indigent status;
- FGT0, FGT1 and FGT2 contribution for poverty;
- FGT0, FGT1 and FGT2 contribution for indigence;
- raw monetary shortfall as diagnostic.

Required person behavior:

- people inherit household poverty/indigence status under the approved method;
- person-level FGT contributions must be explicitly defined as inherited household contribution or omitted; never silently reinterpret household welfare as individual welfare.

Kernel restrictions:

- standard library only unless a concrete need proves otherwise;
- no files/network;
- no geography;
- no weights/aggregation;
- no models or transforms;
- no manifests/packaging.

Adversarial tests:

- zero welfare;
- welfare exactly at the line;
- welfare above the line;
- invalid/negative/non-finite values;
- missing or duplicate household/person IDs;
- unsupported age/sex domain;
- household with no members;
- CBA > CBT rejection;
- FGT values bounded and analytically known for simple examples.

DoD: the scientific object can be tested with a few dataclasses and numbers, with no repository plumbing.

## P3 — v2 upstream contracts

**Mission:** define and prove the exact producer handoffs needed by P2/P4 without forcing sibling repos to depend on poverty internals.

Target logical interfaces:

1. population/frame;
2. welfare estimates;
3. poverty method;
4. poverty lines.

Special requirements:

- remove poverty-region assignment from the intrinsic Census-frame contract;
- require welfare in approved linear monetary units before poverty consumes it;
- separate frame vintage from estimation period;
- define optional joint welfare-draw representation;
- preserve exact IDs and immutable release identity.

P3 should be coordinated with `samplerCensoARG`, model promotion/inference and the basket/line producer.

## P4 — generic estimation design

**Mission:** separate measurement from population estimation.

Required:

- consume P2 micro contributions;
- explicit household/person universes;
- explicit weight/design contract;
- arbitrary declared group keys rather than hard-coding `department_2010` into the estimator;
- FGT0/1/2 weighted estimands;
- national reconciliation where a hierarchy is explicitly supplied;
- coverage and denominator QA;
- fail closed when requested counts/totals are not identified by the frame/design contract.

First acceptance application: `department_2010`.

## P5 — uncertainty propagation

**Mission:** make uncertainty an explicit capability without manufacturing information.

Candidate supported inputs:

- joint welfare draws;
- repeated-imputation draws;
- replicate weights;
- other approved representations with documented estimands.

Candidate outputs:

- point estimate;
- standard error;
- interval;
- CV;
- number/type of draws/replicates;
- publishability/quality status.

Hard rule: when only point welfare and one weight exist, uncertainty fields remain unavailable rather than fabricated.

## P6 — official EPH method-parity benchmark

**Mission:** validate the poverty method independently of Census inference.

Use an exact official EPH release/frame and observed household income with the exact method/lines for a bounded published period.

Compare compatible aggregates to INDEC published poverty/indigence results and document all known reasons exact byte-for-byte equality may not be expected.

This wave should test:

- adult equivalence;
- household-income concept;
- CBA/CBT application;
- equality semantics;
- household/person inheritance;
- survey-weight semantics.

No Census modeling in this wave.

## P7 — welfare-model downstream validation

**Mission:** evaluate a promoted welfare model on the object of interest: poverty.

Where direct EPH poverty can be computed, compare model-derived poverty with direct estimates using a bounded scorecard such as:

- bias;
- RMSE/MAE of poverty and indigence rates;
- rank correlation across domains;
- calibration slope/intercept;
- interval coverage when uncertainty is supplied;
- worst-domain diagnostics.

This is evidence for model promotion/deployment quality, not a new training loop inside poverty.

## P8 — first real governed small-area poverty release

**Mission:** combine exact approved parent releases into one real research poverty estimate product.

Required:

- exact population/frame release;
- exact welfare release;
- exact method release;
- exact line release;
- explicit estimation period and frame vintage;
- FGT estimands;
- uncertainty fields only where supported;
- QA and limitations;
- no maps inside the scientific release;
- detached verification.

Do not label as official INDEC poverty statistics.

## P9 — legacy decommission / repository thinning

Only after successor paths are proven:

- move historical notebooks/data/results under an explicit legacy surface;
- remove active dependence on `data/geo/` and `data/claves_electoral/`;
- retire runtime GeoJSON/map production;
- classify employment/nowcasting notebooks as historical or migrate them to their correct owner;
- remove v1 adapter/model-transform code that no supported release still requires.

Preserve scientific provenance and regression evidence.

## P10 — public/research consumer surface

Expose poverty-estimate releases through thin consumers:

- inspection summaries;
- tidy download contracts;
- Atlas/public site integration;
- citation/limitations metadata;
- reproducible examples.

Visualization never becomes the poverty authority.

## Promotion/ownership rule

If a contract primitive is generic across multiple empirical domains, assess it for `empirical-data-contracts`. If a geometry capability appears, it belongs in `argentina-geography`/`spatial-data-foundation`. Do not grow poverty into a generic framework merely because it was the first consumer.

## Program-level Definition of Done

The v2 program is mature when:

1. the poverty method is a versioned first-class object;
2. the measurement kernel is pure and FGT-based;
3. sampler/inference handoffs do not require poverty-specific upstream hacks;
4. frame vintage and estimation period are distinct;
5. welfare reaches poverty already in approved linear monetary units;
6. uncertainty is propagated when supplied and absent when not justified;
7. direct EPH parity evidence exists;
8. one real small-area research release exists with quality diagnostics;
9. old geography/electoral/model/nowcast responsibilities are no longer on the active runtime path.
