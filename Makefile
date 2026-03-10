.PHONY: hygiene status smoke

status:
	git status --short --branch

hygiene:
	./scripts/repo_hygiene_report.sh

smoke:
	./scripts/smoke_repo.sh
