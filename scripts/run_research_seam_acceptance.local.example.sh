#!/usr/bin/env bash
set -euo pipefail

# Example invocation for the first real local acceptance run. Paths mirror the
# evidence packet captured on 2026-09-11 and remain overrideable by editing the
# command rather than being embedded in library code.
python scripts/run_research_seam_acceptance.py \
  --sampler /media/matias/Elements1/CENSO_work/samples/census-sample-2024-0839713eafea8d1b \
  --semantic /media/matias/Elements1/CENSO_work/derived/eph-cpv2010-semantic-plane-2024q3-v1 \
  --q7 /home/matias/repos/encuestador-de-hogares/science/2026-09-11/results/q7_predictive_distribution \
  --q8 /home/matias/repos/encuestador-de-hogares/science/2026-09-11/results/q8_census_commissioning \
  --eph /home/matias/data/poverty-integration-20260910/eph-releases/eph-2024-q3-3b6a7a15c4af \
  --baskets /home/matias/repos/old/canastasINDEC/data/CB_Reg_defl_Q.csv \
  --department-region data/info/DPTO_PROV_Region.csv \
  --output /home/matias/data/poverty-integration-20260911/first-real-seam \
  --monetary-scalar 0.011493967206201482
