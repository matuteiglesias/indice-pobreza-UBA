# 2024-Q3 commissioning handoff

`COMMISSIONING_CLOSURE_2024Q3.json` is the machine-readable closure receipt
for Cloud A2. `COMMISSIONING_CLOSURE_2024Q3_EVIDENCE_INDEX.json` records the
local real-data evidence IDs, hashes, and source paths used to produce it.

The evidence payloads remain local under `/home/matias/data`; they are not
duplicated into the repository. Cloud A2 must resolve the referenced
artifacts, validate their hashes against the receipt, and update registry
statuses only where the evidence licenses it.

Closed commissioning questions are not recurring pipeline stages. They rerun
only after an upstream invalidation trigger recorded in the registry.
