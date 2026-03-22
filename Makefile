SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -euo pipefail -c

MAIN_BRANCH ?= main

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

.PHONY: release
release: install_deps check build
	@set -euo pipefail; \
	if [ -z "$(MAIN_BRANCH)" ]; then \
		echo "❌ MAIN_BRANCH is empty"; \
		exit 1; \
	fi; \
	if [ -z "$(V)" ]; then \
		echo "❌ V is empty"; \
		exit 1; \
	fi; \
	if ! git diff --exit-code || ! git diff --cached --exit-code; then \
		echo "❌ Working tree is dirty"; \
		exit 1; \
	fi; \
	git fetch --prune origin; \
	HEAD_SHA=$$(git rev-parse HEAD); \
	MAIN_SHA=$$(git rev-parse origin/$(MAIN_BRANCH)); \
	if [ "$$HEAD_SHA" != "$$MAIN_SHA" ]; then \
		echo "❌ Not at origin/$(MAIN_BRANCH)"; \
		exit 1; \
	fi; \
	TAG=v$(V); \
	if git rev-parse -q --verify "refs/tags/$$TAG"; then \
		echo "❌ Tag $$TAG already exists locally"; \
		exit 1; \
	fi; \
	if git ls-remote --exit-code --tags origin "refs/tags/$$TAG"; then \
		echo "❌ Tag $$TAG already exists on origin"; \
		exit 1; \
	fi; \
	echo "🚀 Releasing $$TAG"; \
	if [[ ! "$(V)" = "$$(uv version --short)" ]]; then \
		uv version "$(V)" --no-sync; \
		git commit -am "chore(release): $$TAG"; \
		git push origin "$(MAIN_BRANCH)"; \
	fi; \
	git tag -a "$$TAG" -m "$$TAG"; \
	git push origin "$$TAG"; \
	echo "✅ Released $$TAG"
