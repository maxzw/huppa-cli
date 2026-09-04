.DEFAULT_GOAL := help

.PHONY: help deploy fmt test

help: ## Show available Make targets
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*## ";} /^[a-zA-Z_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deploy: ## Install the current checkout as a global editable uv tool
	uv tool install --force --editable .

fmt: ## Run formatters and linters via pre-commit
	uv run pre-commit run --all-files

test: ## Run tests with pytest
	uv run pytest
