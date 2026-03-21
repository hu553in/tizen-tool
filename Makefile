SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -euo pipefail -c

.PHONY: install_deps
install_deps:
	uv sync --all-groups --frozen

.PHONY: check_deps_updates
check_deps_updates:
	uv tree --outdated --depth=1 | grep latest

.PHONY: check_deps_vuln
check_deps_vuln:
	uv run pysentry-rs .

.PHONY: lint
lint:
	uv run ruff format
	uv run ruff check --fix

.PHONY: check_types
check_types:
	uv run ty check .

.PHONY: check
check:
	uv run prek --all-files --hook-stage pre-commit

.PHONY: build
build:
	uv build
