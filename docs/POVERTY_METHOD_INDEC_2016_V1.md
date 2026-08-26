# Poverty method `argentina.indec-line-poverty-2016@v1`

## Purpose

This is the first versioned poverty-method object owned by this repository. It freezes the scientific semantics expected by the new measurement kernel without changing the legacy v1 release path.

It is **not** an INDEC software product and must not be cited as official statistics. It is a project method designed to be compatible with the official Argentine line-poverty core documented by INDEC, with clearly labeled analytical extensions.

Machine-readable authority:

`configs/poverty_methods/indec-line-poverty-2016-v1.json`

## Official core adopted

The method follows INDEC's line-poverty structure:

1. adult-equivalent units are assigned from age and sex;
2. household adult equivalents are summed;
3. CBA per adult equivalent is multiplied by that sum to obtain the household indigence line;
4. CBT per adult equivalent is multiplied by the same sum to obtain the household poverty line;
5. the relevant welfare concept is household total family income;
6. household income is compared with the household-specific CBA/CBT;
7. the resulting household classification extends to the people living in that household.

Primary source: INDEC, *La medición de la pobreza y la indigencia en la Argentina*, Metodología INDEC Nº 22 (2016). The document explicitly describes CBA/CBT, adult equivalents, comparison to household total family income and extension of the household classification to its members.

The current INDEC poverty/canasta pages and 2026 `INDEC Informa` continue to describe the same core and publish the operational adult-equivalence table.

## Equality semantics

INDEC's general incidence language states that households whose income **does not exceed** (`no supera`) the CBA/CBT are below the indigence/poverty lines. Examples in detailed reports often use the wording `inferior`/below.

For this project method v1, equality is frozen as:

```text
indigent = household_welfare <= household_cba
poor     = household_welfare <= household_cbt
```

This is no longer a free runtime switch.

Why freeze it now:

- the public methodological definition uses `no supera`;
- exact equality in continuous monetary data is usually a measure-zero edge, but deterministic code still needs a rule;
- parity testing can later provide empirical evidence about the exact operational convention.

If P6 official-parity work demonstrates that a different operational rule is required, the correction must be a new method version with regression evidence, not a hidden configuration change.

## Adult-equivalence domain

The v1 method uses canonical sex labels:

```text
female
male
```

Producer-specific codes such as `1`/`2` are adapter concerns and must not leak into the pure method.

Age is completed years. The current INDEC operational table published in `INDEC Informa` uses:

- `<1 year` = `0.35` for both sexes;
- age-specific values from 1 through 17;
- ranges 18–29, 30–45, 46–60, 61–75;
- `more than 75` as the terminal open-ended range.

The machine-readable contract therefore represents age `76+` with an open upper bound.

### Historical fixture correction

The existing v1 candidate adult-equivalence fixture expanded the terminal ranges through an arbitrary maximum age 110 and assigned age 76 to the `61–75` coefficient. That fixture is retained as v1 regression evidence, but it is **not** the authority for the new method.

The new method fixes the boundary explicitly:

```text
female: 61–75 -> 0.67; 76+ -> 0.63
male:   61–75 -> 0.83; 76+ -> 0.74
```

No old output is silently rewritten by P1.

## Welfare concept

The method boundary requires an already-approved **linear monetary household total-family-income concept** compatible with the poverty lines.

The poverty method does not define how a machine-learning prediction becomes that welfare concept. Log inversion, retransformation bias correction, calibration, clipping/censoring and Census scoring belong upstream.

P2 receives household welfare, not a research-model latent prediction.

## FGT analytical extension

The official-compatible core above defines the poverty/indigence thresholds and status. This project additionally standardizes Foster–Greer–Thorbecke contributions for downstream estimation:

For welfare `y`, line `z > 0`, and `alpha >= 0`:

```text
shortfall = max((z - y) / z, 0)
FGT(alpha) contribution = shortfall ** alpha when y <= z, else 0
```

with the conventional explicit handling:

```text
FGT0 = 1 if poor/indigent under the method comparison, else 0
FGT1 = normalized shortfall
FGT2 = squared normalized shortfall
```

The method also permits a raw positive monetary shortfall:

```text
max(z - y, 0)
```

FGT1/FGT2 and this positive-shortfall diagnostic are project analytical extensions. Their presence does not imply that INDEC publishes them as its canonical headline poverty outputs.

## Person semantics

Persons inherit the status of their household, matching the official line-poverty logic.

P2 may expose person contributions for FGT0 directly through inherited status. Any person-level FGT1/FGT2 must be documented as inherited household shortfall, not as a claim that individual welfare was independently compared with an individual line.

## Poverty-line source is separate

This method does not contain monthly/quarterly CBA/CBT values.

A real run requires a separate exact poverty-line release that supplies CBA/CBT per adult equivalent for the applicable threshold area and period, with matching currency/price reference.

This separation lets the method remain stable while poverty lines evolve through time.

## Sources inspected for P1

- INDEC (2016), *La medición de la pobreza y la indigencia en la Argentina*, Metodología Nº 22: `https://www.indec.gob.ar/ftp/cuadros/sociedad/EPH_metodologia_22_pobreza.pdf`
- INDEC, current Canasta básica page: `https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-43-149`
- INDEC Informa, April 2026, poverty methodology/adult-equivalence appendix: `https://www.indec.gob.ar/ftp/cuadros/publicaciones/indec_informa_04_26.pdf`

Retrieval/review date for this method decision: 2026-08-26.

## Non-goals of P1

P1 does not:

- acquire real CBA/CBT releases;
- change the current v1 synthetic poverty release;
- perform Census or EPH adaptation;
- aggregate survey weights;
- compute official parity;
- claim FGT1/FGT2 as INDEC headline statistics.
