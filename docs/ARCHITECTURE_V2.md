# Poverty Estimation v2 — target architecture

## Status

This document defines the target scientific boundary for the next evolution of `indice-pobreza-UBA`. It is an architecture authority, not a claim that every v2 contract or estimator already exists.

The current v1 runtime remains valid while v2 capabilities are introduced behind explicit contracts and regression tests.

## Mission

The repository is the terminal scientific authority that turns an already-governed population/frame, already-deployed welfare estimates, an approved poverty method and compatible poverty lines into reproducible poverty estimands, validation evidence and release artifacts.

The repository should become *smaller in upstream responsibilities* and *stronger in scientific responsibility*.

It should answer:

- What exactly does `poor` or `indigent` mean under a named method?
- What is the poverty line for this household and period?
- What poverty estimand is being reported?
- What population/frame and welfare release does it refer to?
- What weighting/design semantics are used?
- What uncertainty can legitimately be reported?
- How well does the method reproduce direct EPH poverty where direct EPH measurement is available?
- Which small-area estimates pass or fail explicit publication-quality diagnostics?

It should not answer by rebuilding upstream data, geography or models.

## Place in the ecosystem

```text
                    SOURCE / PRODUCER LAYERS

   argentina-geography        samplerCensoARG
          |                         |
          | geographic IDs          | population/frame release
          |                         |
          +------------+------------+
                       |
                       v
             Census inference/deployment
                       ^
                       |
              promoted income model
                       ^
                       |
              income-modeling-eph
                       |
                       v
                welfare estimates

 canastas/official lines -----> poverty lines
                              \
 poverty method ----------------+----> indice-pobreza-UBA
                                      measurement
                                      estimation
                                      uncertainty propagation
                                      validation
                                      releases
                                             |
                                             v
                                   Atlas / research / API
```

`income-modeling-eph` may own research and promotion evidence. A deployment/scoring surface may own execution over a Census frame. Poverty consumes the resulting welfare artifact; it does not import the research model repository at run time.

## Four direct scientific dependencies

The target v2 boundary is expressed as four logical inputs. Exact artifact names may evolve during producer work, but their semantics must not collapse into each other.

### 1. Population/frame

Minimum semantic content:

- stable `person_id` and `household_id`;
- household membership;
- age and sex needed by the poverty method;
- geographic/domain IDs needed for grouping or threshold-area resolution;
- `frame_vintage`;
- sampling/inclusion/weight semantics;
- optional replicate/design information if available;
- provenance and limitations.

The frame does **not** own poverty-line regions as an intrinsic Census geography. A poverty-line threshold area is resolved by a separate versioned binding if it is not already an authoritative source field.

### 2. Welfare estimates

Minimum semantic content:

- exact person/household namespace compatible with the frame;
- approved welfare concept;
- linear monetary amount appropriate for poverty comparison;
- currency and price reference;
- welfare/estimation period;
- provenance to model/scoring execution;
- estimation status/classification;
- optional joint predictive draws or another explicit uncertainty representation.

The poverty layer does not exponentiate a log-model output or invent retransformation/calibration. That responsibility must be resolved before the handoff.

### 3. Poverty method

A versioned scientific definition containing at least:

- methodology identity and source/provenance;
- adult-equivalence table/rules;
- household welfare concept;
- household threshold construction;
- poverty and indigence comparison semantics;
- rule by which people inherit household status;
- definitions of canonical poverty-gap/FGT quantities;
- supported demographic domain;
- explicit deviations, if any, from the referenced official method.

Method ambiguity is resolved here and versioned, rather than exposed forever as arbitrary switches.

### 4. Poverty lines

A versioned temporal/territorial threshold product containing at least:

- threshold-area identity;
- period;
- CBA and CBT per adult equivalent;
- currency and price reference;
- methodology/source identity;
- observed/derived status and limitations.

A poverty run must never infer a missing threshold or silently substitute a different period/region.

## Temporal model

The v1 lock historically required the Census sample period to equal the poverty-estimation period. The v2 model separates at least:

```text
frame_vintage            e.g. 2010
welfare_period           e.g. 2024-Q1
poverty_line_period      e.g. 2024-Q1
estimation_period        e.g. 2024-Q1
model_training_window    upstream lineage only
```

Compatibility is a scientific assertion, not string equality across unrelated clocks.

A CPV-2010-derived frame used for 2024-Q1 remains a CPV-2010 frame. Any projection from that frame to a later population concept must have its own explicit policy/provenance.

## Scientific layers inside the repository

### A. Poverty measurement

A pure deterministic layer:

```text
people + adult-equivalence method
                 |
                 v
 household adult-equivalent units
                 +
 threshold-area poverty line
                 |
                 v
        household CBA / CBT
                 +
        household welfare
                 |
                 v
 poverty / indigence status
 FGT contribution(s)
```

It must know nothing about Git, manifests, files, EPH, Census acquisition, modeling libraries, maps or sampling algorithms.

### B. Poverty estimation

A separate layer combines micro poverty contributions with an explicit design/weight contract and grouping domains.

Initial outputs may remain weighted rates. The target language is general poverty estimands:

- FGT0 / incidence;
- FGT1 / normalized poverty gap;
- FGT2 / severity, when scientifically authorized;
- counts or totals only when the population/design contract supports them.

Group keys are inputs. `department_2010` is an important first application, not the identity of the estimator itself.

### C. Uncertainty propagation

The repository may propagate uncertainty that is supplied in a scientifically interpretable form, such as:

- joint welfare draws;
- replicate weights;
- repeated imputation/model draws;
- another explicitly approved representation.

Outputs may include standard error, intervals, CV and quality status when justified.

If uncertainty inputs are absent, the release must say so and must not synthesize precision statistics.

### D. Validation

Validation is first-class scientific output, not only software QA.

Two important gates are planned:

1. **method parity**: apply this repository's method to direct EPH observed welfare/weights and compare compatible aggregates with INDEC publications;
2. **model-to-poverty validation**: evaluate whether a promoted welfare model recovers poverty/indigence patterns where direct EPH estimates can be computed.

The second gate evaluates the downstream object of interest, not only income prediction error.

## Canonical output

The long-run public scientific product should be an immutable poverty-estimate release rather than a collection of maps or micro classifications.

Conceptual tidy grain:

```text
estimation_period
frame_vintage
geography_level
geography_id
universe                 household | person
concept                  poverty | indigence
estimand                 fgt0 | fgt1 | fgt2 | count
estimate
standard_error           nullable when unsupported
ci_lower                 nullable
ci_upper                 nullable
cv                       nullable
coverage
quality_status
population_frame_release
welfare_release
poverty_method_release
poverty_line_release
```

Micro classifications may remain a controlled intermediate/research artifact. They are not the primary public interface.

## Geography boundary

Poverty uses IDs, not geometry.

No active scientific runtime should:

- read shapefiles/GeoJSON merely to calculate poverty;
- perform a spatial join;
- decide whether INDEC/CEUR/IGN is canonical;
- own electoral circuits or crosswalks;
- construct a map.

A publication consumer may join a poverty-estimate table to an exact `argentina-geography` release after the scientific estimate is complete.

## Legacy disposition

The repository contains substantial historical material from the era when the project also performed acquisition, modeling, geography, nowcasting and publication work.

These materials remain evidence until an explicit decommission wave:

- `data/geo/`;
- `data/claves_electoral/`;
- notebook-era `data/results/`;
- employment/nowcasting/geospatial notebooks;
- map/publication helpers that are not required for the scientific runtime.

Do not delete them opportunistically during P0-P2. First establish the new authority and prove the successor paths.

## Compatibility with v1

P0-P2 are evolutionary.

- v1 locks/releases/tests remain regression evidence;
- the current pure household kernel may be wrapped or reused while v2 semantics are proven;
- new FGT primitives should not silently change existing v1 release outputs;
- producer migrations happen only after concrete handoff contracts are proven.

## Success criterion

This architecture is succeeding when improvements in Census sampling, geography and income modeling make this repository *simpler*, while this repository becomes more capable at method definition, estimands, uncertainty, validation and scientific release governance.
