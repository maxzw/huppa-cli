.DEFAULT_GOAL := help

.PHONY: help fmt test

help: ## Show available Make targets
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*## ";} /^[a-zA-Z_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

fmt: ## Run formatters and linters via pre-commit
	poetry run pre-commit run --all-files

test: ## Run tests with pytest
	poetry run pytest
