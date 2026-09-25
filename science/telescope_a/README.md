# Telescope A — observed EPH poverty microscope

## Scope

Telescope A is a bounded validation harness for one question:

> Starting from one observed EPH quarter, how does the project obtain a poverty estimate from the household/person microdata?

The first implementation covers **T0–T2 only**:

- **T0 — design closure:** freeze the observed-data poverty contract;
- **T1 — Q3 raw microscope:** make every retained household auditable from EPH fields to poverty state;
- **T2 — Q3 estimator:** aggregate those measured household/person contributions with `PONDIH` through the existing v2 estimator.

This is research validation, not an official INDEC poverty publication.

## Scientific contract

Telescope A v1 freezes these choices:

| Item | Decision |
|---|---|
| Welfare concept | observed household `ITF` |
| Missing household income | negative/non-numeric `ITF` is excluded; zero is valid welfare |
| Weight | household `PONDIH` |
| Household composition | actual EPH person rows joined by period + `CODUSU` + `NRO_HOGAR` |
| Adult equivalents | existing `argentina.indec-line-poverty-2016@v1` method |
| Threshold geography | EPH `REGION` mapped to the six canonical basket regions |
| Basket units | nominal current ARS per equivalent adult |
| Quarter line | arithmetic mean of the three monthly nominal regional CBA/CBT observations |
| Indigence | `ITF <= household_CBA` under the governed method |
| Poverty | `ITF <= household_CBT` under the governed method |
| Person poverty | inherited from the person's household |
| FGT | existing pure measurement kernel |
| Population estimation | existing `estimation_v2` with household `PONDIH` |
| `P47T` | accounting/completeness diagnostic only; never the primary T0–T2 welfare concept |
| ML / Census | out of scope |

No IPC conversion is performed. Raw EPH `ITF` and the supplied nominal monthly basket observations remain on the same current-peso scale.

## Repository boundary

Telescope A does **not** acquire EPH or basket sources. The runner receives explicit local files. It also does not reimplement poverty science.

The flow is:

```text
explicit EPH household/person files
              +
explicit monthly nominal CBA/CBT snapshots
              |
              v
Telescope A EPH normalization + audit surface
              |
              v
existing poverty method + measurement kernel
              |
              v
existing estimation_v2 using PONDIH
              |
              v
households.parquet + summary.json + report.md
```

The runner must not grow model inference, Census mappings, price-index production, shapefile work, or poverty publication logic.

## Input expectations

The household file must contain:

```text
CODUSU NRO_HOGAR ANO4 TRIMESTRE REGION AGLOMERADO IX_TOT ITF IPCF PONDIH
```

The person file must contain:

```text
CODUSU NRO_HOGAR COMPONENTE ANO4 TRIMESTRE CH04 CH06 P47T
```

The CBA and CBT inputs are explicit monthly wide CSV snapshots with:

```text
indice_tiempo
cuyo
gran_buenos_aires
noreste
noroeste
pampeana
patagonia
```

A compatible date column named `period`, `date`, or `Fecha` is also accepted. Exactly the three months of the requested quarter must be present once each.

## Identity

Quarter must be part of identity. Telescope A uses:

```text
household_id = ANO4 : TRIMESTRE : CODUSU : NRO_HOGAR
person_id    = ANO4 : TRIMESTRE : CODUSU : NRO_HOGAR : COMPONENTE
```

This prevents households observed in different EPH waves from collapsing when later work concatenates quarters.

## Structural failures versus diagnostics

The T0–T2 runner fails closed on conditions that would make the resulting poverty number structurally ambiguous:

- duplicate household or person identity;
- person rows referring to absent households;
- household rows with no person records;
- disagreement between `IX_TOT` and actual person-row membership;
- unknown EPH region code;
- unsupported/invalid age or sex for a retained household;
- nonpositive/nonfinite `PONDIH` for a retained household;
- incomplete requested-month coverage in CBA/CBT inputs;
- nonpositive basket values or CBA above CBT.

The following remain visible diagnostics and are never silently repaired:

- `ITF` versus complete-household `sum_P47T`;
- `IPCF` versus `ITF / member_count`;
- incomplete `P47T` households;
- source households excluded because `ITF` is invalid;
- the raw versus retained `PONDIH` mass;
- households nearest the CBA and CBT boundaries.

In particular, Telescope A does **not** assert `ITF == sum(P47T)` as a prerequisite. It measures that relationship first.

## T1 household microscope

The primary local artifact is one row per retained household with roughly:

```text
period
household_id
CODUSU
NRO_HOGAR
REGION
AGLOMERADO
basket_region
member_count_records
IX_TOT
membership_match
adult_equivalents
ITF
IPCF
sum_P47T
ITF_valid
P47T_complete
itf_minus_sum_p47t
ipcf_reconstructed
ipcf_delta
PONDIH
cba_per_ae
cbt_per_ae
household_cba
household_cbt
indigent
poor
poor_non_indigent
nonpoor
indigence_fgt0
indigence_fgt1
indigence_fgt2
poverty_fgt0
poverty_fgt1
poverty_fgt2
```

The table is an inspection surface, not a new public release contract.

## T2 estimation semantics

`estimation_v2` receives one household weight per measured household:

```text
analysis_weight = PONDIH
```

For households, the national denominator is therefore:

```text
sum_h PONDIH_h
```

Because person contributions inherit the household state and every member is passed to the estimator, the person denominator is automatically:

```text
sum_h PONDIH_h * member_count_h
```

The runner verifies both denominators explicitly after estimation. It groups first by the six EPH basket regions and relies on `estimation_v2` to reconcile those cells to a national estimate.

`estimation_v2.coverage == 1` means complete coverage **within the measured T1 cohort**. Telescope A separately reports source retention so that this cannot be confused with complete coverage of all raw EPH households.

## Outputs

A run writes only:

```text
households.parquet
summary.json
report.md
```

No manifest/checksum/release framework is introduced at T0–T2. If Telescope outputs later become stable inputs to another system, that can be decided separately.

## Deliberately deferred

Not part of this branch:

- A1/A2/A3 diagnostic waterfall;
- multiple quarters;
- semester pooling;
- comparison with published INDEC aggregates;
- exact interview/reference-month line assignment;
- timing sensitivity envelopes;
- ML/predictive welfare;
- Census inference;
- uncertainty estimation.
