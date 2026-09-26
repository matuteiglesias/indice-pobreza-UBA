# Poverty ecosystem commissioning dashboard

This surface is a **scientific observability/commissioning layer**, not a new estimator.

It assembles already-governed artifacts and small pinned external validation benchmarks into
one ephemeral diagnostic frame and a set of presentation-ready figures.

## Boundary

It may:

- compare project outputs with official INDEC benchmark snapshots;
- derive deterministic diagnostic ratios such as `CBT/CBA` and `welfare/CBT`;
- group already-defined poverty states by age/region for validation;
- concatenate Telescope A/B/C evidence across periods;
- summarize already-released department facts for visual diagnostics;
- emit PNG and tidy CSV companions.

It does **not**:

- create new poverty estimands;
- train, tune or calibrate welfare models;
- alter sampling/design weights;
- reimplement Telescope A/B/C;
- acquire or become authority for official INDEC statistics;
- become a parent input to poverty estimation;
- perform public Atlas rendering or geometry work.

The diagnostic frame is ephemeral. Its rows are projections of exact parents and retain
source roles/identities for audit.

## Ten frozen figure intents

1. **Headline poverty reality check** — official semester poverty/indigence and compatible project results.
2. **People below the lines** — absolute poor/indigent person counts.
3. **Basket / Engel mechanics** — regional CBA, CBT and `CBT/CBA`.
4. **Income in CBT units** — observed EPH vs OOF point distribution of household welfare / household CBT.
5. **Labor-market reality check** — official activity/employment/unemployment rates plus reconstructed EPH population stocks.
6. **Poverty by age** — inherited person poverty/indigence states across 0–14, 15–29, 30–64, 65+.
7. **Poverty by region** — EPH regional FGT0 paths.
8. **Telescope B bridge** — observed → OOF point → predictive.
9. **Telescope C transport** — EPH point/predictive ↔ Census point/predictive.
10. **Department dispersion** — population-weighted quantiles of released department person-poverty FGT0.

A figure is never silently fabricated. Its status is one of:

```text
ready
blocked_missing_parent
failed_gate
```

## Agglomerate commissioning bridge

`compare_agglomerates.py` is a separate G7 diagnostic for the first-class EPH-agglomerate surface. It compares already-released observed EPH and Census-target predictive releases and requires:

- exact 32-ID `eph_agglomerate` inventory;
- exact `eph_coverage/EPH_TOTAL` aggregate declaration on both releases;
- person FGT0 poverty/indigence facts from the same period.

It emits deltas only. It does not recompute poverty, recalibrate weights, invent an administrative parent, or convert EPH coverage into a national estimate. This comparator is intentionally outside the ten frozen dashboard figure intents until the longitudinal G5/G7 commissioning surface is stable.

## Outputs

A run writes:

```text
diagnostic_frame.csv
run_manifest.json
figure_status.csv
figures/
  01_headline_poverty.csv
  01_headline_poverty.png
  ...
report.md
```

Every PNG has a tidy CSV companion containing exactly the plotted values. These are easy
to embed in Render, Vercel, notebooks, reports or the Atlas without importing Poverty's
runtime.

## Local execution

Copy and edit the example config:

```bash
cp science/commissioning/config.example.json /tmp/poverty-commissioning.json
PYTHONPATH=src python science/commissioning/run.py \
  --config /tmp/poverty-commissioning.json \
  --output /home/matias/data/poverty-commissioning-2024q1-2025q4
```

All local parents are optional at the config level so development can proceed incrementally.
Missing parents block only the figures that need them. Scientific contract failures fail the
affected adapter rather than coercing data into a plausible picture.

## Benchmark snapshots

`benchmarks/indec_poverty_semester.csv` and `benchmarks/indec_labor_quarter.csv`
are tiny, manually pinned validation snapshots from INDEC publications. They are not
scientific inputs to Poverty. Source URLs and publication dates are retained in
`benchmarks/sources.json`.

If benchmark maintenance grows beyond this bounded use, it should move to a proper
public-data producer rather than expanding this directory into an acquisition system.
