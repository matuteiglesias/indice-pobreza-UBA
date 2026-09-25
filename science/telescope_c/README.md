# Telescope C — EPH -> Census-derived target transport

Telescope C is a research commissioning diagnostic. It asks what happens when the
**same frozen P1-R model system** leaves the EPH validation domain and scores the
governed Census-derived target-year sample.

It is not a new poverty estimator and it does not perform domain adaptation.

## Why it is person-first

The governed target-year Census sampler changes department-level **person mass**
through household selection, while leaving downstream `analysis_weight` unset.
It does not define target-year household totals. Telescope C therefore treats
person indigence/poverty as its primary transport estimand.

## C0 — matched-model contract

For every outer fold `f`:

```text
(M_-f, G_-f)

held-out EPH fold f  <->  all Census target persons
```

The upstream evidence must first prove that re-fitting `M_-f` reproduces the
persisted P1-R EPH OOF predictions. The exact Q7 nested residual ECDF `G_-f`
is then reused unchanged.

No monetary scalar is applied. Poverty lines are the same nominal Q3 regional
CBA/CBT machinery commissioned by Telescope A.

## C1 — domain x representation bridge

For each state `I / PNI / N`:

```text
                 POINT       PREDICTIVE
EPH
Census target
```

The aggregate Census matched-model result is the fold-weighted mean of the five
all-Census scores, using the EPH validation folds' person-PONDIH mass shares.
This keeps the model-mixture comparison tied to the exact EPH validation design.

Telescope C reports:

- point transport;
- predictive transport;
- EPH residual effect;
- Census residual effect;
- transport x residual interaction.

EPH observed poverty remains an anchor but is not part of the 2x2 identity.

## C2 — threshold-margin transport

For CBA and CBT, Telescope C compares the distributions of:

```text
mu
line
mu / line
line - mu
G_-f(line - mu)
```

and decomposes point/predictive transport through common threshold-centric
`mu/line` bands. This directly measures whether the Census target places more
mass where the unchanged residual ECDF has large crossing probability.

## C3 — support localization

Consumes upstream cross-fitted equal-prior EPH-vs-Census support probabilities.

It defines Census-person-mass quintiles from most EPH-like to least EPH-like,
applies those same cutpoints to EPH, and reports within-bin point/predictive
rates plus each bin's exact contribution to the aggregate transport delta.

It also reports:

- the weakest target 5%;
- the upstream hard `support_weak` flag.

Support scores are diagnostics, never production weights.

## C4 — optional coarse composition standardization

As a commissioning counterfactual only:

```text
EPH observed
    -> EPH observed standardized to Census support-quintile shares
    -> Census matched point
    -> Census matched predictive
```

This is one-dimensional standardization on the diagnostic overlap score. It is
not claimed to reproduce the full 21-dimensional Census covariate distribution.

## Outputs

```text
bridge.csv
transport_decomposition.csv
margin_summary.csv
margin_bins.csv
support_bins.csv
support_hard.csv
support_tail.csv
composition_standardization.csv
summary.json
report.md
```

## Deferred

Telescope C does not:

- condition or replace residual distributions;
- fit density-ratio production weights;
- perform entropy balancing;
- refit P1-R with transport weights;
- construct national household weights;
- use P2;
- use CPV-2022;
- claim the donor-frame within-department composition is observed in 2024.
