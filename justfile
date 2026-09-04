default:
    @just --list

deploy:
    uv tool install --force --editable .

fmt:
    uv run pre-commit run --all-files

test:
    uv run pytest
