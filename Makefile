SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -euo pipefail -c

.PHONY: install-deps
install-deps:
	uv sync --all-groups --frozen

.PHONY: lint
lint:
	uv run ruff format
	uv run ruff check --fix

.PHONY: check-types
check-types:
	uv run ty check .

.PHONY: check
check:
	uv run prek --all-files --hook-stage pre-commit

# Project-specific

.PHONY: build
build:
	uv build

.PHONY: release-patch
release-patch: install-deps check
	uv run semantic-release --strict version --no-changelog --no-vcs-release --patch

.PHONY: release-minor
release-minor: install-deps check
	uv run semantic-release --strict version --no-changelog --no-vcs-release --minor

.PHONY: release-major
release-major: install-deps check
	uv run semantic-release --strict version --no-changelog --no-vcs-release --major
