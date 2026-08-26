.PHONY: hygiene status smoke policy-check contracts-check contracts-smoke adapters-smoke method-check measurement-check v2-contracts-check estimation-check v2-release-smoke atlas-contract-smoke

PYTHON := PYTHONPATH=src python

status:
	git status --short --branch

hygiene:
	./scripts/repo_hygiene_report.sh

smoke:
	@echo "Structural notebook smoke only (not a scientific execution)."
	./scripts/smoke_repo.sh

policy-check:
	$(PYTHON) scripts/check_production_source_policy.py

contracts-check:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m unittest tests.test_contracts
	$(PYTHON) -m poverty_pipeline validate-lock fixtures/slice-locks/contracts-only.yaml >/dev/null

contracts-smoke:
	$(PYTHON) -m unittest tests.test_contracts tests.test_census_adapter

adapters-smoke:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	mkdir -p build/qa
	$(PYTHON) -m poverty_pipeline validate-lock fixtures/slice-locks/contracts-only.yaml --qa-output build/qa/contracts-only.json >/dev/null
	@echo "Synthetic adapter QA written; scientific_execution_performed=false"

method-check:
	$(PYTHON) -m unittest tests.test_poverty_method

measurement-check: method-check
	$(PYTHON) -m unittest tests.test_fgt_measurement

v2-contracts-check: measurement-check
	$(PYTHON) -m unittest tests.test_contracts_v2

estimation-check: v2-contracts-check
	$(PYTHON) -m unittest tests.test_estimation_v2

v2-release-smoke: estimation-check
	rm -rf build/v2/poverty-estimate-fixture-v2 build/v2/poverty-estimate-fixture-v2-rerun
	$(PYTHON) scripts/build_v2_estimate_fixture.py --output build/v2/poverty-estimate-fixture-v2
	cp build/v2/poverty-estimate-fixture-v2/checksums.sha256 build/v2/checksums-first.sha256
	$(PYTHON) -c "from poverty_pipeline.release_v2 import verify_estimate_release; verify_estimate_release('build/v2/poverty-estimate-fixture-v2')"
	rm -rf build/v2/poverty-estimate-fixture-v2
	$(PYTHON) scripts/build_v2_estimate_fixture.py --output build/v2/poverty-estimate-fixture-v2
	cmp build/v2/checksums-first.sha256 build/v2/poverty-estimate-fixture-v2/checksums.sha256

atlas-contract-smoke: v2-release-smoke
	rm -rf build/v2/atlas-province-contract-fixture
	$(PYTHON) scripts/build_v2_estimate_fixture.py --geography-level province_2010 --output build/v2/atlas-province-contract-fixture
	$(PYTHON) -c "import json; from pathlib import Path; from poverty_pipeline.release_v2 import verify_estimate_release; p=Path('build/v2/atlas-province-contract-fixture'); verify_estimate_release(p); j=json.loads((p/'geography_join_contract.json').read_text()); c=json.loads((p/'capabilities.json').read_text()); assert j['joinable_geography_levels']==['province_2010']; assert c['scientific_status']=='synthetic_fixture'"
	@echo "Atlas consumer contract fixture: passed"

.PHONY: poverty-release-smoke local-artifact-inventory
poverty-release-smoke:
	rm -rf build/releases/synthetic-visible-poverty-2024q1 build/releases/synthetic-visible-poverty-2024q1-rerun build/inspection
	$(PYTHON) scripts/build_poverty_release_fixtures.py
	$(PYTHON) -m poverty_pipeline run-lock fixtures/slice-locks/poverty-release-synthetic.json
	$(PYTHON) -m poverty_pipeline verify-release build/releases/synthetic-visible-poverty-2024q1/v1
	POVERTY_RELEASE_DIR=build/releases/synthetic-visible-poverty-2024q1/v1 python -c "import notebooks.released_outputs as r; assert len(r.load_released_tables()) == 5"
	$(PYTHON) -m poverty_pipeline inspect-release build/releases/synthetic-visible-poverty-2024q1/v1 --output build/inspection
	cp build/releases/synthetic-visible-poverty-2024q1/v1/aggregates_tidy.csv build/aggregates-first.csv
	rm -rf build/releases/synthetic-visible-poverty-2024q1
	$(PYTHON) -m poverty_pipeline run-lock fixtures/slice-locks/poverty-release-synthetic.json
	cmp build/aggregates-first.csv build/releases/synthetic-visible-poverty-2024q1/v1/aggregates_tidy.csv

local-artifact-inventory:
	$(PYTHON) scripts/inventory_local_artifacts.py

.PHONY: release-index
release-index:
	$(PYTHON) scripts/index_releases.py
