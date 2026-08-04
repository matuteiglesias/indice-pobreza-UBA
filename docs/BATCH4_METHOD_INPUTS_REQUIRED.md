# Batch 4 method inputs required after sprint zero

Sprint zero is **contracts only**. The household poverty kernel remains blocked
until the following producer artifacts and decisions are explicitly approved by
Matías:

1. **Selected slice period** — choose the real period; the synthetic `2024-Q4`
   fixture is not a selection.
2. **Census sample and weight policy** — provide an immutable Census release and
   approve its universe, sampling design, weights, and permitted estimands.
3. **Person-income release and adequacy** — accept a prediction release in the
   exact Census sample-ID namespace and decide whether its domain and
   retransformation are adequate. An EPH model is not presumed Census-compatible.
4. **Adult-equivalence source** — provide an immutable, versioned producer
   artifact with approved sex/age domains, boundary rules, provenance, and QA.
5. **Regional basket source** — provide an immutable CBA/CBT release with complete
   region-period coverage, units, price reference, methodology, and QA.
6. **Threshold policy** — decide strict versus inclusive equality for poverty and
   indigence comparisons.
7. **Gap sign** — define the subtraction order and interpretation for income gaps.
8. **Geography** — approve the department vintage and decide whether any spatial
   output is in scope; geography publication must remain a separate action.

The next merge order is: approved basket and adult-equivalence adapters, then an
approved pure household kernel. Aggregation and publication remain later scopes.

