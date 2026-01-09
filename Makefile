# floe Platform Makefile
# =======================
#
# Test targets for K8s-native testing infrastructure.
# See TESTING.md for detailed documentation.
#
# Quick Start:
#   make kind-up      # Create Kind cluster and deploy services
#   make test-unit    # Run unit tests (fast, no K8s required)
#   make test         # Run all tests in K8s
#   make kind-down    # Cleanup Kind cluster

.PHONY: help
help: ## Show this help message
	@echo "floe Platform - Development Commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests (unit + integration)"
	@echo "  make test-unit       Run unit tests only (fast, no K8s)"
	@echo "  make test-integration Run integration tests (requires K8s)"
	@echo "  make test-e2e        Run E2E tests (requires K8s + full stack)"
	@echo ""
	@echo "Cluster Management:"
	@echo "  make kind-up         Create Kind cluster and deploy services"
	@echo "  make kind-down       Destroy Kind cluster"
	@echo ""
	@echo "Quality Checks:"
	@echo "  make lint            Run linting (ruff)"
	@echo "  make typecheck       Run type checking (mypy)"
	@echo "  make check           Run all CI checks (lint + typecheck + test)"
	@echo ""
	@echo "Use 'make <target>' to run a command."

# ============================================================
# Cluster Management
# ============================================================

.PHONY: kind-up
kind-up: ## Create Kind cluster and deploy test services
	@echo "Creating Kind cluster..."
	@./testing/k8s/setup-cluster.sh

.PHONY: kind-down
kind-down: ## Destroy Kind cluster
	@echo "Destroying Kind cluster..."
	@./testing/k8s/cleanup-cluster.sh

# ============================================================
# Test Targets
# ============================================================

.PHONY: test
test: test-unit test-integration ## Run all tests (unit + integration)
	@echo "All tests completed."

.PHONY: test-unit
test-unit: ## Run unit tests only (fast, no K8s required)
	@echo "Running unit tests..."
	@./testing/ci/test-unit.sh

.PHONY: test-integration
test-integration: ## Run integration tests (requires Kind cluster)
	@echo "Running integration tests..."
	@./testing/ci/test-integration.sh

.PHONY: test-e2e
test-e2e: ## Run E2E tests (requires Kind cluster + full stack)
	@echo "Running E2E tests..."
	@./testing/ci/test-e2e.sh

# ============================================================
# Quality Checks
# ============================================================

.PHONY: lint
lint: ## Run linting (ruff check + format check)
	@echo "Running linting..."
	@uv run ruff check .
	@uv run ruff format --check .

.PHONY: typecheck
typecheck: ## Run type checking (mypy --strict)
	@echo "Running type checking..."
	@uv run mypy --strict packages/

.PHONY: check
check: lint typecheck test ## Run all CI checks (lint + typecheck + test)
	@echo "All checks passed!"

# ============================================================
# Development Helpers
# ============================================================

.PHONY: fmt
fmt: ## Format code with ruff
	@echo "Formatting code..."
	@uv run ruff format .
	@uv run ruff check --fix .

.PHONY: clean
clean: ## Clean generated files
	@echo "Cleaning generated files..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf coverage.xml coverage_html test-logs 2>/dev/null || true
	@echo "Done."

.PHONY: traceability
traceability: ## Check requirement traceability coverage
	@echo "Checking requirement traceability..."
	@uv run python -m testing.traceability --all --threshold 80
