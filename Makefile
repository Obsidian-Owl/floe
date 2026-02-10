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
	@echo "Helm Charts:"
	@echo "  make helm-deps       Update Helm chart dependencies"
	@echo "  make helm-lint       Lint Helm charts"
	@echo "  make helm-template   Render templates (ENV=dev|staging|prod)"
	@echo "  make helm-test       Run Helm tests (RELEASE=..., NAMESPACE=...)"
	@echo "  make helm-install-dev Install floe-platform for development"
	@echo "  make helm-install-test Install floe with test values (CI/CD)"
	@echo "  make helm-upgrade-test Upgrade test installation"
	@echo "  make helm-uninstall-test Uninstall test installation"
	@echo "  make helm-test-infra Verify test infrastructure health"
	@echo "  make helm-uninstall  Uninstall floe (NAMESPACE=... required)"
	@echo ""
	@echo "Demo:"
	@echo "  make demo            Deploy platform with all 3 demo data products (PRODUCTS=...)"
	@echo "  make demo-stop       Stop demo and clean up resources"
	@echo ""
	@echo "Agent Memory (Cognee):"
	@echo "  make cognee-health   Check Cognee Cloud connectivity"
	@echo "  make cognee-init     Initialize knowledge graph (PROGRESS=1, RESUME=1)"
	@echo "  make cognee-search   Search knowledge graph (QUERY=\"...\" required)"
	@echo "  make cognee-codify   Extract and index Python docstrings (PATTERN=\"...\")"
	@echo "  make cognee-sync     Sync changed files (FILES=\"...\", DRY_RUN=1, ALL=1)"
	@echo ""
	@echo "MCP Server (Claude Code Integration):"
	@echo "  make cognee-mcp-start  Start Cognee MCP server (DETACH=1, PORT=...)"
	@echo "  make cognee-mcp-stop   Stop running MCP server"
	@echo "  make cognee-mcp-config Generate MCP configuration (INSTALL=1)"
	@echo ""
	@echo "Agent Memory Operations:"
	@echo "  make cognee-coverage   Analyze coverage (filesystem vs indexed)"
	@echo "  make cognee-drift      Detect drift (stale/outdated content)"
	@echo "  make cognee-repair     Repair drifted entries (DRY_RUN=1)"
	@echo "  make cognee-reset      Full reset (CONFIRM=1 required)"
	@echo "  make cognee-test       Run quality validation (VERBOSE=1, THRESHOLD=N)"
	@echo ""
	@echo "Setup:"
	@echo "  make setup-hooks     Install chained git hooks (bd + pre-commit + Cognee)"
	@echo "  make install-fusion  Install official dbt Fusion CLI from dbt Labs"
	@echo "  make check-fusion    Check if dbt Fusion CLI is installed"
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

.PHONY: test-integration-image
test-integration-image: ## Build test runner Docker image
	@echo "Building test runner Docker image..."
	@docker build -t floe-test-runner:latest -f testing/Dockerfile .
	@echo "Image built: floe-test-runner:latest"

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
	@uv run mypy --strict packages/ testing/

.PHONY: check
check: lint typecheck test ## Run all CI checks (lint + typecheck + test)
	@echo "All checks passed!"

# ============================================================
# Helm Chart Targets
# ============================================================

.PHONY: helm-deps
helm-deps: ## Update Helm chart dependencies
	@echo "Updating Helm chart dependencies..."
	@helm dependency update charts/floe-platform
	@helm dependency update charts/floe-jobs

.PHONY: helm-lint
helm-lint: ## Lint Helm charts
	@echo "Linting Helm charts..."
	@helm lint charts/floe-platform --values charts/floe-platform/values.yaml
	@helm lint charts/floe-jobs --values charts/floe-jobs/values.yaml
	@echo "Helm linting passed!"

.PHONY: helm-template
helm-template: ## Render Helm templates (ENV=dev|staging|prod)
	@echo "Rendering Helm templates..."
	@mkdir -p .helm-output
	@if [ -n "$(ENV)" ] && [ -f "charts/floe-platform/values-$(ENV).yaml" ]; then \
		helm template floe-platform charts/floe-platform \
			--values charts/floe-platform/values.yaml \
			--values charts/floe-platform/values-$(ENV).yaml \
			--output-dir .helm-output/$(ENV); \
	else \
		helm template floe-platform charts/floe-platform \
			--values charts/floe-platform/values.yaml \
			--output-dir .helm-output/default; \
	fi
	@echo "Templates rendered to .helm-output/"

.PHONY: helm-test
helm-test: ## Run Helm tests (requires deployed release, RELEASE=name, NAMESPACE=ns)
	@if [ -z "$(RELEASE)" ]; then \
		echo "ERROR: RELEASE is required. Usage: make helm-test RELEASE=floe NAMESPACE=floe-dev"; \
		exit 1; \
	fi
	@if [ -z "$(NAMESPACE)" ]; then \
		echo "ERROR: NAMESPACE is required. Usage: make helm-test RELEASE=floe NAMESPACE=floe-dev"; \
		exit 1; \
	fi
	@echo "Running Helm tests for $(RELEASE) in $(NAMESPACE)..."
	@helm test $(RELEASE) --namespace $(NAMESPACE)

.PHONY: helm-install-dev
helm-install-dev: helm-deps ## Install floe-platform for development
	@echo "Installing floe-platform for development..."
	@uv run floe platform deploy --env dev --chart charts/floe-platform

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall floe-platform (NAMESPACE=ns required)
	@if [ -z "$(NAMESPACE)" ]; then \
		echo "ERROR: NAMESPACE is required. Usage: make helm-uninstall NAMESPACE=floe-dev"; \
		exit 1; \
	fi
	@echo "Uninstalling floe from $(NAMESPACE)..."
	@helm uninstall floe-platform --namespace $(NAMESPACE)

.PHONY: helm-integration-test
helm-integration-test: helm-deps ## Run Helm integration tests in Kind cluster
	@echo "Running Helm integration tests..."
	@# Ensure Kind cluster exists
	@if ! kind get clusters 2>/dev/null | grep -q floe-test; then \
		echo "Creating Kind cluster..."; \
		kind create cluster --name floe-test --wait 120s; \
	fi
	@# Install charts
	@echo "Installing floe-platform chart..."
	@helm upgrade --install floe-platform charts/floe-platform \
		--namespace floe-test --create-namespace \
		--values charts/floe-platform/values.yaml \
		--skip-schema-validation \
		--values charts/floe-platform/values-dev.yaml \
		--wait --timeout 5m
	@# Run Helm tests
	@echo "Running Helm tests..."
	@helm test floe-platform --namespace floe-test --timeout 5m
	@echo "Helm integration tests passed!"

.PHONY: helm-install-test
helm-install-test: helm-deps ## Install floe-platform with test values (requires Kind cluster)
	@echo "Installing floe-platform with test configuration..."
	@uv run floe platform deploy --env test --chart charts/floe-platform
	@echo "Installing floe-jobs with test configuration..."
	@helm upgrade --install floe-jobs-test charts/floe-jobs \
		--namespace floe-test \
		--values charts/floe-jobs/values-test.yaml \
		--wait --timeout 5m
	@echo "Test infrastructure installed!"

.PHONY: helm-upgrade-test
helm-upgrade-test: helm-deps ## Upgrade floe-platform test installation
	@echo "Upgrading floe-platform test installation..."
	@uv run floe platform deploy --env test --chart charts/floe-platform
	@helm upgrade floe-jobs-test charts/floe-jobs \
		--namespace floe-test \
		--values charts/floe-jobs/values-test.yaml \
		--wait --timeout 5m
	@echo "Test infrastructure upgraded!"

.PHONY: helm-uninstall-test
helm-uninstall-test: ## Uninstall floe test installation
	@echo "Uninstalling floe test installation..."
	@helm uninstall floe-jobs-test --namespace floe-test 2>/dev/null || true
	@helm uninstall floe-platform --namespace floe-test 2>/dev/null || true
	@kubectl delete namespace floe-test --ignore-not-found --wait=false
	@echo "Test infrastructure uninstalled!"

.PHONY: helm-test-infra
helm-test-infra: ## Verify test infrastructure is healthy
	@echo "Checking test infrastructure health..."
	@kubectl get pods -n floe-test --no-headers 2>/dev/null || { echo "Test namespace not found. Run: make helm-install-test"; exit 1; }
	@echo "Checking Polaris..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=polaris -n floe-test --timeout=60s 2>/dev/null || echo "Polaris not ready"
	@echo "Checking PostgreSQL..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -n floe-test --timeout=60s 2>/dev/null || echo "PostgreSQL not ready"
	@echo "Checking MinIO..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=minio -n floe-test --timeout=60s 2>/dev/null || echo "MinIO not ready"
	@echo "Test infrastructure health check complete!"

# ============================================================
# Demo Targets
# ============================================================

.PHONY: demo demo-stop

demo: ## Deploy platform and run all 3 demo data products with dashboards
	@echo "=== Starting floe Platform Demo ==="
	@echo "Ensuring Kind cluster is running..."
	$(MAKE) kind-up
	@echo "Installing floe-platform Helm chart with demo overrides..."
	@uv run floe platform deploy --env dev --chart ./charts/floe-platform \
		--values ./charts/floe-platform/values-demo.yaml
	@echo "Compiling demo data products..."
	@if [ -n "$(PRODUCTS)" ]; then \
		for product in $(shell echo $(PRODUCTS) | tr ',' ' '); do \
			echo "Compiling $$product..."; \
			uv run floe compile demo/$$product/floe.yaml || exit 1; \
		done; \
	else \
		for product in customer-360 iot-telemetry financial-risk; do \
			echo "Compiling $$product..."; \
			uv run floe compile demo/$$product/floe.yaml || exit 1; \
		done; \
	fi
	@echo "Deploying to Dagster..."
	@echo "=== Demo Ready ==="
	@echo "Dagster UI:    http://localhost:3000"
	@echo "Polaris:       http://localhost:8181"
	@echo "Marquez:       http://localhost:5001"
	@echo "Jaeger:        http://localhost:16686"
	@echo "Grafana:       http://localhost:3001"
	@echo "MinIO Console: http://localhost:9001"

demo-stop: ## Stop demo and clean up resources
	@echo "=== Stopping floe Platform Demo ==="
	@helm uninstall floe-platform -n floe-dev --ignore-not-found
	@echo "Demo stopped. Run 'make kind-down' to destroy cluster."

# ============================================================
# Development Helpers
# ============================================================

.PHONY: setup-hooks
setup-hooks: ## Install chained git hooks (bd + pre-commit)
	@./scripts/setup-hooks.sh

.PHONY: install-fusion
install-fusion: ## Install official dbt Fusion CLI from dbt Labs
	@echo "Installing official dbt Fusion CLI..."
	@curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh | sh -s -- --update
	@echo "dbt Fusion CLI installed to ~/.local/bin/dbt"
	@echo "Ensure ~/.local/bin is in your PATH"

.PHONY: check-fusion
check-fusion: ## Check if dbt Fusion CLI is installed and show version
	@if command -v dbt >/dev/null 2>&1 && dbt --version 2>&1 | grep -q "fusion"; then \
		echo "dbt Fusion CLI found:"; \
		dbt --version; \
	elif test -x "$$HOME/.local/bin/dbt"; then \
		echo "dbt Fusion CLI found at ~/.local/bin/dbt:"; \
		$$HOME/.local/bin/dbt --version; \
	else \
		echo "dbt Fusion CLI not found"; \
		echo "Run 'make install-fusion' to install"; \
		exit 1; \
	fi

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

# ============================================================
# Agent Memory (Cognee Integration)
# ============================================================

.PHONY: cognee-check-env
cognee-check-env: ## Verify required Cognee environment variables are set
	@if [ -z "$$COGNEE_API_KEY" ]; then \
		echo "ERROR: COGNEE_API_KEY environment variable is not set" >&2; \
		echo "Get your API key from https://www.cognee.ai/" >&2; \
		exit 1; \
	fi
	@if [ -z "$$OPENAI_API_KEY" ]; then \
		echo "ERROR: OPENAI_API_KEY environment variable is not set" >&2; \
		echo "Get your API key from https://platform.openai.com/" >&2; \
		exit 1; \
	fi

.PHONY: cognee-health
cognee-health: cognee-check-env ## Run Cognee Cloud health check
	@echo "Checking Cognee Cloud connectivity..."
	@cd devtools/agent-memory && uv run agent-memory health

.PHONY: cognee-init
cognee-init: cognee-check-env ## Initialize Cognee knowledge graph (PROGRESS=1 for progress bar, RESUME=1 to resume)
	@echo "Initializing Cognee knowledge graph..."
	@cd devtools/agent-memory && uv run agent-memory init \
		$(if $(filter 1,$(PROGRESS)),--progress,) \
		$(if $(filter 1,$(RESUME)),--resume,)

.PHONY: cognee-search
cognee-search: cognee-check-env ## Search knowledge graph (QUERY="..." required)
ifndef QUERY
	$(error QUERY is required. Usage: make cognee-search QUERY="your search query")
endif
	@echo "Searching knowledge graph..."
	@cd devtools/agent-memory && uv run agent-memory search "$(QUERY)"

.PHONY: cognee-codify
cognee-codify: cognee-check-env ## Extract and index Python docstrings (PATTERN="..." for specific files)
	@echo "Extracting and indexing Python docstrings..."
	@cd devtools/agent-memory && uv run agent-memory codify \
		$(if $(PATTERN),--pattern "$(PATTERN)",)

.PHONY: cognee-sync
cognee-sync: cognee-check-env ## Sync changed files to knowledge graph (FILES="...", DRY_RUN=1, ALL=1)
	@echo "Syncing files to knowledge graph..."
	@cd devtools/agent-memory && uv run agent-memory sync \
		$(if $(FILES),--files $(FILES),) \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,) \
		$(if $(filter 1,$(ALL)),--all,)

# ============================================================
# MCP Server (Claude Code Integration)
# ============================================================

.PHONY: cognee-mcp-start
cognee-mcp-start: cognee-check-env ## Start Cognee MCP server (DETACH=1, PORT=...)
	@echo "Starting Cognee MCP server..."
	@./scripts/cognee-mcp-start \
		$(if $(filter 1,$(DETACH)),--detach,) \
		$(if $(PORT),--port $(PORT),)

.PHONY: cognee-mcp-stop
cognee-mcp-stop: ## Stop running Cognee MCP server
	@echo "Stopping Cognee MCP server..."
	@./scripts/cognee-mcp-start --stop

.PHONY: cognee-mcp-config
cognee-mcp-config: ## Generate MCP configuration (INSTALL=1 to update .claude/mcp.json)
	@cd devtools/agent-memory && uv run agent-memory mcp-config \
		$(if $(filter 1,$(INSTALL)),--install,)

# ============================================================
# Agent Memory Operations (Coverage, Drift, Reset, Test)
# ============================================================

.PHONY: cognee-coverage
cognee-coverage: cognee-check-env ## Analyze coverage (filesystem vs indexed content)
	@echo "Analyzing knowledge graph coverage..."
	@cd devtools/agent-memory && uv run agent-memory coverage

.PHONY: cognee-drift
cognee-drift: cognee-check-env ## Detect drift (stale/outdated indexed content)
	@echo "Detecting drift in knowledge graph..."
	@cd devtools/agent-memory && uv run agent-memory drift

.PHONY: cognee-repair
cognee-repair: cognee-check-env ## Repair drifted entries (DRY_RUN=1 for preview)
	@echo "Repairing drifted entries..."
	@cd devtools/agent-memory && uv run agent-memory repair \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,)

.PHONY: cognee-reset
cognee-reset: cognee-check-env ## Full reset (CONFIRM=1 required for safety)
ifndef CONFIRM
	$(error CONFIRM=1 required. This will DELETE all indexed content. Usage: make cognee-reset CONFIRM=1)
endif
	@echo "Resetting knowledge graph..."
	@cd devtools/agent-memory && uv run agent-memory reset --confirm

.PHONY: cognee-test
cognee-test: cognee-check-env ## Run quality validation tests (VERBOSE=1, THRESHOLD=N)
	@echo "Running quality validation tests..."
	@cd devtools/agent-memory && uv run agent-memory test \
		$(if $(filter 1,$(VERBOSE)),--verbose,) \
		$(if $(THRESHOLD),--threshold $(THRESHOLD),)
