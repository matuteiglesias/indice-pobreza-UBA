.PHONY: hygiene status

status:
	git status --short --branch

hygiene:
	./scripts/repo_hygiene_report.sh
