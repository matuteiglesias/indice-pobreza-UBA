.PHONY: hygiene status smoke contracts-check contracts-smoke adapters-smoke

PYTHON := PYTHONPATH=src python

status:
	git status --short --branch

hygiene:
	./scripts/repo_hygiene_report.sh

smoke:
	@echo "Structural notebook smoke only (not a scientific execution)."
	./scripts/smoke_repo.sh

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
