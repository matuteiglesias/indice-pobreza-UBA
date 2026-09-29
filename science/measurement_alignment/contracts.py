"""Frozen contracts for observed-EPH Measurement Alignment M1/M3."""
from __future__ import annotations

M1_POLICIES = ("T0_current_quarter_mean", "T1_previous_month", "Tm_current_previous_midpoint")
M3_POLICIES = ("official", "engho17_level_only", "engho17_level_plus_trajectory")
BASELINE_POLICY = {"M1": M1_POLICIES[0], "M3": M3_POLICIES[0]}
REGIONS = ("gran_buenos_aires","pampeana","noreste","noroeste","cuyo","patagonia")
BASKET_ARTIFACT_TYPE = "research.argentina-regional-baskets/v1"
BASKET_METHOD_ID = "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"
ENGEL_ARTIFACT_TYPE = "research.argentina-regional-baskets-engel-sensitivity/v1"
ENGEL_METHOD_ID = "research.argentina-regional-baskets-engel-sensitivity/engho17-fixed-base-regional-ipc-v1"
ENGEL_REFERENCE_METHOD_ID = "research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2"
ANALYSIS_START = "2022-Q1"
ANALYSIS_END = "2025-Q4"
STATUS = "research_validation_not_official_statistics"
NONRESPONSE_CALIBRATION = False
REPORTING_DRIFT_M2 = "deferred"
