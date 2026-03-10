PYTHON ?= python3
CONFIG ?= config/pipeline.yaml
PYTHONPATH := src

.PHONY: show-config smoke dirs

dirs:
	mkdir -p artifacts/logs artifacts/runs \
		artifacts/stage_01_predict \
		artifacts/stage_02_poverty \
		artifacts/stage_03_stats \
		artifacts/stage_04_geo

show-config:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/show_config.py --config $(CONFIG)

smoke: dirs
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/run_smoke.py --config $(CONFIG)