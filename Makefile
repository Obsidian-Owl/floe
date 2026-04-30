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
	@echo "  make test-e2e        Run E2E tests in-cluster (auto-detects Kind/DevPod)"
	@echo "  make test-e2e-full   Run standard + destructive E2E suites sequentially"
	@echo "  make test-e2e-host   Run E2E tests via host port-forwards (legacy)"
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
	@echo "Documentation:"
	@echo "  make docs-build      Build documentation site"
	@echo "  make docs-serve      Serve documentation site locally"
	@echo "  make docs-validate   Validate docs navigation and build"
	@echo ""
	@echo "Helm Charts:"
	@echo "  make helm-deps       Update Helm chart dependencies"
	@echo "  make helm-lint       Lint Helm charts"
	@echo "  make helm-template   Render templates (ENV=dev|staging|prod)"
	@echo "  make helm-validate   Validate manifests with kubeconform"
	@echo "  make helm-test       Run Helm tests (RELEASE=..., NAMESPACE=...)"
	@echo "  make helm-install-dev Install floe-platform for development"
	@echo "  make helm-install-test Install floe with test values (CI/CD)"
	@echo "  make helm-package-flux-artifact Package the vendored floe-platform chart for Flux"
	@echo "  make helm-upgrade-test Upgrade test installation"
	@echo "  make helm-uninstall-test Uninstall test installation"
	@echo "  make helm-test-infra Verify test infrastructure health"
	@echo "  make helm-uninstall  Uninstall floe (NAMESPACE=... required)"
	@echo ""
	@echo "Demo:"
	@echo "  make compile-demo    Compile dbt models + generate definitions for demo products"
	@echo "  make build-demo-image Build Dagster demo Docker image"
	@echo "  make demo            Deploy demo via DevPod (requires running workspace)"
	@echo "  make demo-stop       Stop demo port-forwards"
	@echo "  make demo-local      Deploy demo locally (requires local Kind cluster)"
	@echo "  make demo-customer-360-validate Validate Customer 360 golden demo evidence"
	@echo ""
	@echo "DevPod (Remote E2E):"
	@echo "  make devpod-setup    One-time Hetzner provider setup from .env"
	@echo "  make devpod-test     Run E2E tests on Hetzner (full lifecycle)"
	@echo "  make devpod-delete   Delete DevPod workspace (stops billing)"
	@echo "  make devpod-status   Show workspace status, tunnels, and cluster health"
	@echo "  make devpod-up       Create/start DevPod workspace on Hetzner"
	@echo "  make devpod-stop     Stop workspace (preserves VM disk)"
	@echo "  make devpod-ssh      SSH into workspace"
	@echo "  make devpod-sync     Sync kubeconfig from workspace to local"
	@echo "  make devpod-tunnels  Forward service ports via SSH"
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
	@echo "  make setup-hooks     Install git hooks (pre-commit + Cognee)"
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
	@SKIP_MONITORING=$${SKIP_MONITORING:-true} ./testing/k8s/setup-cluster.sh

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
	@scripts/with-public-docker-config.sh docker build -t floe-test-runner:latest -f testing/Dockerfile .
	@echo "Image built: floe-test-runner:latest"

.PHONY: test-e2e
test-e2e: ## Run E2E tests in-cluster as K8s Job (auto-detects Kind/DevPod)
	@echo "Running E2E tests in-cluster..."
	@./testing/ci/test-e2e-cluster.sh

.PHONY: test-e2e-full
test-e2e-full: ## Run standard + destructive E2E suites sequentially
	@echo "Running full E2E test suite..."
	@./testing/ci/test-e2e-full.sh

.PHONY: test-e2e-host
test-e2e-host: ## Run E2E tests via host port-forwards (legacy, requires running services)
	@echo "Running E2E tests (host port-forwards)..."
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
# Documentation
# ============================================================

.PHONY: docs-build docs-serve docs-validate
docs-build: ## Build documentation site
	@npm --prefix docs-site ci
	@npm --prefix docs-site run build

docs-serve: ## Serve documentation site locally
	@npm --prefix docs-site install
	@npm --prefix docs-site run dev -- --host 127.0.0.1

docs-validate: ## Validate docs navigation and build
	@uv run python testing/ci/validate-docs-navigation.py
	@npm --prefix docs-site ci
	@npm --prefix docs-site run validate

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

.PHONY: helm-package-flux-artifact
helm-package-flux-artifact: ## Package the vendored floe-platform chart used by Flux
	@echo "Packaging floe-platform Flux artifact..."
	@mkdir -p charts/floe-platform/flux-artifacts
	@rm -f charts/floe-platform/flux-artifacts/floe-platform.tgz
	@rm -f charts/floe-platform/flux-artifacts/floe-platform-*.tgz
	@helm dependency build charts/floe-platform >/dev/null
	@package_path=$$(helm package charts/floe-platform --destination charts/floe-platform/flux-artifacts | awk '{print $$NF}'); \
		mv "$${package_path}" charts/floe-platform/flux-artifacts/floe-platform.tgz
	@echo "Packaged charts/floe-platform/flux-artifacts/floe-platform.tgz"

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

# =============================================================================
# Containerized Helm validation tools (security-hardening AC-5/6/7)
# Images pinned inline in each recipe — do NOT use :latest.
# To bump versions: update helm-validate, helm-security, helm-test-unit
# recipes below. Pinned images live in the recipe body (not Make variables)
# so the structural test can find them without Make expansion.
# =============================================================================

.PHONY: helm-validate
helm-validate: ## Validate rendered manifests against K8s 1.28 schema (containerized kubeconform)
	@echo "Validating Helm templates with containerized kubeconform (ghcr.io/yannh/kubeconform:v0.6.7)..."
	@echo "  Validating with values.yaml (production defaults)..."
	@helm template floe-platform charts/floe-platform --values charts/floe-platform/values.yaml | \
		scripts/with-public-docker-config.sh docker run --rm -i ghcr.io/yannh/kubeconform:v0.6.7 \
			--strict --kubernetes-version 1.28.0 --ignore-missing-schemas -summary
	@echo "  Validating with values-test.yaml (test overrides)..."
	@helm template floe-platform charts/floe-platform --values charts/floe-platform/values-test.yaml | \
		scripts/with-public-docker-config.sh docker run --rm -i ghcr.io/yannh/kubeconform:v0.6.7 \
			--strict --kubernetes-version 1.28.0 --ignore-missing-schemas -summary
	@echo "Helm template validation passed!"

.PHONY: helm-security
helm-security: ## Scan rendered manifests with containerized kubesec
	@echo "Scanning Helm templates with containerized kubesec (kubesec/kubesec:v2.14.1)..."
	@helm template floe-platform charts/floe-platform --values charts/floe-platform/values.yaml | \
		docker run --rm -i kubesec/kubesec:v2.14.1 scan /dev/stdin
	@echo "kubesec scan complete."

.PHONY: helm-test-unit
helm-test-unit: helm-deps ## Run helm-unittest chart template tests (containerized)
	@echo "Running containerized helm-unittest (helmunittest/helm-unittest:3.19.0-1.0.3)..."
	@docker run --rm --user $$(id -u):$$(id -g) -v $(PWD)/charts:/apps helmunittest/helm-unittest:3.19.0-1.0.3 floe-platform
	@echo "Helm unit tests passed!"

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
	@uv run floe platform deploy --env dev --chart charts/floe-platform \
		$(DEMO_IMAGE_HELM_SET_ARGS)

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
	@# Install charts via floe platform deploy
	@echo "Installing floe-platform chart..."
	@uv run floe platform deploy --env dev --chart charts/floe-platform \
		--namespace floe-test --timeout 5m \
		$(DEMO_IMAGE_HELM_SET_ARGS)
	@# Run Helm tests
	@echo "Running Helm tests..."
	@helm test floe-platform --namespace floe-test --timeout 5m
	@echo "Helm integration tests passed!"

.PHONY: helm-install-test
helm-install-test: helm-deps ## Install floe-platform with test values (requires Kind cluster)
	@echo "Installing floe-platform with test configuration..."
	@uv run floe platform deploy --env test --chart charts/floe-platform \
		$(DEMO_IMAGE_HELM_SET_ARGS)
	@echo "Installing floe-jobs with test configuration..."
	@helm upgrade --install floe-jobs-test charts/floe-jobs \
		--namespace floe-test \
		--values charts/floe-jobs/values-test.yaml \
		--wait --timeout 5m
	@echo "Test infrastructure installed!"

.PHONY: helm-upgrade-test
helm-upgrade-test: helm-deps ## Upgrade floe-platform test installation
	@echo "Upgrading floe-platform test installation..."
	@uv run floe platform deploy --env test --chart charts/floe-platform \
		$(DEMO_IMAGE_HELM_SET_ARGS)
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
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=polaris -n floe-test --timeout=60s 2>/dev/null || echo "Polaris not ready"
	@echo "Checking PostgreSQL..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=postgresql -n floe-test --timeout=60s 2>/dev/null || echo "PostgreSQL not ready"
	@echo "Checking MinIO..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=minio -n floe-test --timeout=60s 2>/dev/null || echo "MinIO not ready"
	@echo "Test infrastructure health check complete!"

# ============================================================
# Demo Targets
# ============================================================

.PHONY: compile-demo build-demo-image demo demo-local demo-stop demo-customer-360-validate

DEMO_MANIFEST ?= demo/manifest.yaml
DEMO_IMAGE_REPOSITORY ?= floe-dagster-demo
DEMO_IMAGE_TAG ?= $(shell python3 testing/ci/resolve-demo-image-ref.py --field tag)
DEMO_IMAGE_REF ?= $(DEMO_IMAGE_REPOSITORY):$(DEMO_IMAGE_TAG)
export FLOE_DEMO_NAMESPACE ?= floe-dev
export FLOE_DEMO_DAGSTER_URL ?= http://localhost:3100
export FLOE_DEMO_MARQUEZ_URL ?= http://localhost:5100
export FLOE_DEMO_JAEGER_URL ?= http://localhost:16686
export FLOE_DEMO_PLATFORM_EXPECTED_SERVICES ?= dagster,polaris,minio,jaeger,marquez
export FLOE_DEMO_COMMAND_TIMEOUT_SECONDS ?= 30
export FLOE_DEMO_DAGSTER_EXPECTED_TEXT
export FLOE_DEMO_LINEAGE_EXPECTED_TEXT
export FLOE_DEMO_TRACING_EXPECTED_TEXT
export FLOE_DEMO_STORAGE_EXPECTED_TEXT
export FLOE_DEMO_DAGSTER_RUN_CHECK_COMMAND
export FLOE_DEMO_LINEAGE_CHECK_COMMAND
export FLOE_DEMO_TRACING_CHECK_COMMAND
export FLOE_DEMO_STORAGE_CHECK_COMMAND
export FLOE_DEMO_CUSTOMER_COUNT_COMMAND
export FLOE_DEMO_LIFETIME_VALUE_COMMAND
DEMO_IMAGE_HELM_SET_ARGS = \
	--set dagster.dagsterWebserver.image.repository=$(DEMO_IMAGE_REPOSITORY) \
	--set dagster.dagsterWebserver.image.tag=$(DEMO_IMAGE_TAG) \
	--set dagster.dagsterDaemon.image.repository=$(DEMO_IMAGE_REPOSITORY) \
	--set dagster.dagsterDaemon.image.tag=$(DEMO_IMAGE_TAG) \
	--set dagster.runLauncher.config.k8sRunLauncher.image.repository=$(DEMO_IMAGE_REPOSITORY) \
	--set dagster.runLauncher.config.k8sRunLauncher.image.tag=$(DEMO_IMAGE_TAG)

compile-demo: ## Compile dbt models and generate Dagster definitions for all demo products
	@echo "Compiling dbt models for all demo products..."
	@# Local-only defaults for dbt compile — real environments must override via env vars.
	@# Credentials match tests/e2e/conftest.py and values-test.yaml (test-only, never production).
	@export FLOE_E2E_POLARIS_ENDPOINT=$${FLOE_E2E_POLARIS_ENDPOINT:-http://localhost:8181/api/catalog}; \
	export FLOE_E2E_POLARIS_CLIENT_ID=$${FLOE_E2E_POLARIS_CLIENT_ID:-demo-admin}; \
	export FLOE_E2E_POLARIS_CLIENT_SECRET=$${FLOE_E2E_POLARIS_CLIENT_SECRET:-demo-secret}; \
	export FLOE_E2E_POLARIS_OAUTH2_URI=$${FLOE_E2E_POLARIS_OAUTH2_URI:-http://localhost:8181/api/catalog/v1/oauth/tokens}; \
	export FLOE_E2E_S3_ENDPOINT=$${FLOE_E2E_S3_ENDPOINT:-localhost:9000}; \
	export FLOE_E2E_S3_USE_SSL=$${FLOE_E2E_S3_USE_SSL:-false}; \
	for product in customer-360 iot-telemetry financial-risk; do \
		echo "Compiling $$product..."; \
		uv run dbt compile --project-dir demo/$$product --profiles-dir demo/$$product || exit 1; \
	done
	@echo "Generating Dagster definitions.py for all demo products..."
	@for product in customer-360 iot-telemetry financial-risk; do \
		echo "Generating definitions for $$product..."; \
		uv run floe platform compile \
			--spec demo/$$product/floe.yaml \
			--manifest $(DEMO_MANIFEST) \
			--output demo/$$product/compiled_artifacts.json \
			--generate-definitions || exit 1; \
	done
	@uv run python testing/ci/validate-demo-compiled-artifacts.py \
		--manifest $(DEMO_MANIFEST) \
		--demo-dir demo
	@echo "All demo products compiled successfully!"

.PHONY: check-manifests
check-manifests: ## Verify committed dbt manifests are not stale
	@echo "Checking dbt manifests are up to date..."
	@git diff --exit-code demo/*/target/manifest.json > /dev/null 2>&1 || \
		{ echo "ERROR: Committed dbt manifests are stale. Run 'make compile-demo' and commit." >&2; exit 1; }
	@echo "Manifests are up to date."

# Multi-arch platform (override with: make build-demo-image DOCKER_PLATFORM=linux/arm64)
DOCKER_PLATFORM ?= linux/amd64

# Extract demo plugin list from manifest.yaml
# - Reads plugin selections from the manifest schema
# - Maps selections through local workspace entry points
# - Includes local workspace dependency closure because Docker installs with --no-deps
DEMO_PLUGINS := $(shell .venv/bin/python scripts/resolve-demo-plugins.py --manifest $(DEMO_MANIFEST))

build-demo-image: compile-demo ## Build Dagster demo Docker image and load to Kind
	@echo "Building Dagster demo Docker image..."
	@echo "  Plugins: $(DEMO_PLUGINS)"
	@echo "  Platform: $(DOCKER_PLATFORM)"
	@echo "  Image: $(DEMO_IMAGE_REF)"
	@scripts/with-public-docker-config.sh docker build -f docker/dagster-demo/Dockerfile \
		--build-arg FLOE_PLUGINS="$(DEMO_PLUGINS)" \
		--platform $(DOCKER_PLATFORM) \
		-t $(DEMO_IMAGE_REF) .
	@echo "Loading image to Kind cluster..."
	@bash -lc 'source testing/ci/common.sh && floe_kind_evict_image "$(DEMO_IMAGE_REF)" "$${KIND_CLUSTER_NAME:-floe-test}"'
	@kind load docker-image $(DEMO_IMAGE_REF) --name $${KIND_CLUSTER_NAME:-floe-test}
	@echo "Demo image built and loaded to Kind successfully!"

demo: ## Deploy demo via DevPod (requires running DevPod workspace)
	@echo "=== Starting floe Platform Demo (DevPod) ==="
	@scripts/devpod-ensure-ready.sh
	@echo "Building demo image inside DevPod..."
	@devpod ssh "$(DEVPOD_WORKSPACE)" -- "cd /workspace && FLOE_DEMO_IMAGE_REPOSITORY=$(DEMO_IMAGE_REPOSITORY) FLOE_DEMO_IMAGE_TAG=$(DEMO_IMAGE_TAG) make build-demo-image"
	@echo "Updating Helm chart dependencies..."
	@helm dependency update charts/floe-platform
	@echo "Deploying Helm chart via tunneled kubectl..."
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" uv run floe platform deploy \
		--env dev --chart ./charts/floe-platform \
		--values ./charts/floe-platform/values-demo.yaml \
		$(DEMO_IMAGE_HELM_SET_ARGS)
	@echo "Starting port-forwards..."
	@if [ -f .demo-pids ]; then \
		kill $$(cat .demo-pids) 2>/dev/null || true; \
		rm -f .demo-pids; \
	fi
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-dagster-webserver 3100:3000 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-polaris 8181:8181 8182:8182 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-minio 9000:9000 9001:9001 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-jaeger-query 16686:16686 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-marquez 5100:5000 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl port-forward svc/floe-platform-otel 4317:4317 4318:4318 -n floe-dev >/dev/null 2>&1 & echo $$! >> .demo-pids
	@echo ""
	@echo "=== Demo Ready ==="
	@echo "Dagster UI:    http://localhost:3100"
	@echo "Polaris:       http://localhost:8181"
	@echo "Marquez:       http://localhost:5100"
	@echo "Jaeger:        http://localhost:16686"
	@echo "MinIO Console: http://localhost:9001"
	@echo "MinIO API:     http://localhost:9000"
	@echo "OTel gRPC:     http://localhost:4317"
	@echo "OTel HTTP:     http://localhost:4318"
	@echo ""
	@echo "Stop with: make demo-stop"

demo-stop: ## Stop demo port-forwards
	@if [ -f .demo-pids ]; then \
		echo "Stopping demo port-forwards..."; \
		kill $$(cat .demo-pids) 2>/dev/null || true; \
		rm -f .demo-pids; \
		echo "Demo port-forwards stopped."; \
	else \
		echo "No demo port-forwards running (.demo-pids not found)."; \
	fi

demo-local: build-demo-image ## Deploy demo locally (requires local Kind cluster)
	@echo "=== Starting floe Platform Demo (local Kind) ==="
	@echo "Ensuring Kind cluster is running..."
	$(MAKE) kind-up
	@echo "Installing floe-platform Helm chart with demo overrides..."
	@uv run floe platform deploy --env dev --chart ./charts/floe-platform \
		--values ./charts/floe-platform/values-demo.yaml \
		$(DEMO_IMAGE_HELM_SET_ARGS)
	@echo "=== Demo Ready ==="
	@echo "Dagster UI:    http://localhost:3000"
	@echo "Polaris:       http://localhost:8181"
	@echo "Marquez:       http://localhost:5001"
	@echo "Jaeger:        http://localhost:16686"
	@echo "Grafana:       http://localhost:3001"
	@echo "MinIO Console: http://localhost:9001"
	@echo ""
	@echo "Stop with: helm uninstall floe-platform -n floe-dev"

demo-customer-360-validate: ## Validate Customer 360 golden demo evidence
	@uv run python -m testing.ci.validate_customer_360_demo

# ============================================================
# Development Helpers
# ============================================================

.PHONY: setup-hooks
setup-hooks: ## Install git hooks (pre-commit + Cognee)
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

# =============================================================================
# DevPod (Remote E2E on Hetzner)
# =============================================================================

DEVPOD_WORKSPACE ?= floe
DEVPOD_PROVIDER ?= hetzner
DEVPOD_DEVCONTAINER ?= .devcontainer/hetzner/devcontainer.json
DEVPOD_KUBECONFIG ?= $(HOME)/.kube/devpod-$(DEVPOD_WORKSPACE).config

.PHONY: devpod-check
devpod-check:
	@command -v devpod >/dev/null 2>&1 || { \
		echo "ERROR: devpod CLI not found in PATH" >&2; \
		echo "  Install: https://devpod.sh/docs/getting-started/install" >&2; \
		echo "  Add provider: devpod provider add mrsimonemms/devpod-provider-hetzner" >&2; \
		exit 1; \
	}

.PHONY: devpod-up
devpod-up: devpod-check ## Create/start DevPod workspace on Hetzner
	@echo "Starting DevPod workspace '$(DEVPOD_WORKSPACE)' on $(DEVPOD_PROVIDER)..."
	@DEVPOD_WORKSPACE="$(DEVPOD_WORKSPACE)" \
		DEVPOD_PROVIDER="$(DEVPOD_PROVIDER)" \
		DEVPOD_DEVCONTAINER="$(DEVPOD_DEVCONTAINER)" \
		bash -c 'source scripts/devpod-source.sh; source_resolved=$$(devpod_resolve_source "$$(pwd)") || exit 1; \
		echo "Using DevPod source: $${source_resolved}"; \
		devpod up "$(DEVPOD_WORKSPACE)" \
		--source "$${source_resolved}" \
		--id "$(DEVPOD_WORKSPACE)" \
		--provider "$(DEVPOD_PROVIDER)" \
		--devcontainer-path "$(DEVPOD_DEVCONTAINER)" \
		--ide none'

.PHONY: devpod-stop
devpod-stop: devpod-check ## Stop DevPod workspace (preserves VM disk)
	@echo "WARNING: Stopped VMs still incur Hetzner billing. Use 'make devpod-delete' to stop all charges." >&2
	@echo "Stopping DevPod workspace '$(DEVPOD_WORKSPACE)'..."
	devpod stop "$(DEVPOD_WORKSPACE)"

.PHONY: devpod-ssh
devpod-ssh: devpod-check ## SSH into DevPod workspace
	devpod ssh "$(DEVPOD_WORKSPACE)"

.PHONY: devpod-sync
devpod-sync: devpod-check ## Sync kubeconfig from DevPod workspace to local
	@bash scripts/devpod-sync-kubeconfig.sh "$(DEVPOD_WORKSPACE)"

.PHONY: devpod-tunnels
devpod-tunnels: ## Forward service ports from DevPod workspace via SSH
	@bash scripts/devpod-tunnels.sh

.PHONY: devpod-setup
devpod-setup: devpod-check ## One-time Hetzner provider setup from .env
	@bash scripts/devpod-setup.sh

.PHONY: devpod-test
devpod-test: devpod-check ## Run E2E tests on Hetzner (full lifecycle)
	@bash scripts/devpod-test.sh

.PHONY: devpod-delete
devpod-delete: devpod-check ## Delete DevPod workspace (stops billing)
	@bash scripts/devpod-tunnels.sh --kill 2>/dev/null || true
	@echo "Deleting DevPod workspace '$(DEVPOD_WORKSPACE)'..."
	devpod delete "$(DEVPOD_WORKSPACE)" --force

.PHONY: devpod-status
devpod-status: devpod-check ## Show workspace status, tunnels, and cluster health
	@echo "=== Workspace Status ==="
	@devpod status "$(DEVPOD_WORKSPACE)" 2>/dev/null || echo "Workspace '$(DEVPOD_WORKSPACE)' not running"
	@echo ""
	@echo "=== Tunnel Status ==="
	@scripts/devpod-tunnels.sh --status 2>/dev/null || echo "No tunnels active"
	@echo ""
	@echo "=== Cluster Health ==="
	@KUBECONFIG="$(DEVPOD_KUBECONFIG)" kubectl cluster-info 2>/dev/null || echo "Cluster not reachable"
