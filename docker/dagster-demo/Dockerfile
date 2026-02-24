# Dagster Demo Image — 3-Stage uv Build
# =======================================
#
# Builds a self-contained Dagster image from python:3.11-slim using uv
# for reproducible, hash-verified dependency resolution. No vendor base
# image — all packages resolved from the workspace lockfile.
#
# Stages:
#   1. export  — uv export produces requirements.txt with hashes
#   2. build   — pip install from requirements.txt + workspace packages
#   3. runtime — minimal image with site-packages + demo products
#
# Build:
#   docker build -f docker/dagster-demo/Dockerfile -t floe-dagster-demo:latest .
#
# Requirements:
#   - Run `make compile-demo` before building (generates definitions.py)
#   - Build context must be the repo root

# =============================================================================
# Stage 1: EXPORT — Produce requirements.txt from workspace lockfile
# =============================================================================
FROM ghcr.io/astral-sh/uv:0.7.2-debian AS export

WORKDIR /build

# Copy lockfile + root pyproject.toml
COPY uv.lock pyproject.toml ./

# Copy ALL workspace member pyproject.toml files (required for --frozen validation).
# uv needs the full workspace metadata to verify lockfile integrity.
COPY packages/floe-core/pyproject.toml packages/floe-core/pyproject.toml
COPY packages/floe-iceberg/pyproject.toml packages/floe-iceberg/pyproject.toml
COPY plugins/floe-alert-alertmanager/pyproject.toml plugins/floe-alert-alertmanager/pyproject.toml
COPY plugins/floe-alert-email/pyproject.toml plugins/floe-alert-email/pyproject.toml
COPY plugins/floe-alert-slack/pyproject.toml plugins/floe-alert-slack/pyproject.toml
COPY plugins/floe-alert-webhook/pyproject.toml plugins/floe-alert-webhook/pyproject.toml
COPY plugins/floe-catalog-polaris/pyproject.toml plugins/floe-catalog-polaris/pyproject.toml
COPY plugins/floe-compute-duckdb/pyproject.toml plugins/floe-compute-duckdb/pyproject.toml
COPY plugins/floe-dbt-core/pyproject.toml plugins/floe-dbt-core/pyproject.toml
COPY plugins/floe-dbt-fusion/pyproject.toml plugins/floe-dbt-fusion/pyproject.toml
COPY plugins/floe-identity-keycloak/pyproject.toml plugins/floe-identity-keycloak/pyproject.toml
COPY plugins/floe-ingestion-dlt/pyproject.toml plugins/floe-ingestion-dlt/pyproject.toml
COPY plugins/floe-lineage-marquez/pyproject.toml plugins/floe-lineage-marquez/pyproject.toml
COPY plugins/floe-network-security-k8s/pyproject.toml plugins/floe-network-security-k8s/pyproject.toml
COPY plugins/floe-orchestrator-dagster/pyproject.toml plugins/floe-orchestrator-dagster/pyproject.toml
COPY plugins/floe-quality-dbt/pyproject.toml plugins/floe-quality-dbt/pyproject.toml
COPY plugins/floe-quality-gx/pyproject.toml plugins/floe-quality-gx/pyproject.toml
COPY plugins/floe-rbac-k8s/pyproject.toml plugins/floe-rbac-k8s/pyproject.toml
COPY plugins/floe-secrets-infisical/pyproject.toml plugins/floe-secrets-infisical/pyproject.toml
COPY plugins/floe-secrets-k8s/pyproject.toml plugins/floe-secrets-k8s/pyproject.toml
COPY plugins/floe-semantic-cube/pyproject.toml plugins/floe-semantic-cube/pyproject.toml
COPY plugins/floe-telemetry-console/pyproject.toml plugins/floe-telemetry-console/pyproject.toml
COPY plugins/floe-telemetry-jaeger/pyproject.toml plugins/floe-telemetry-jaeger/pyproject.toml

# Target plugin list — overridden by Makefile via --build-arg
ARG FLOE_PLUGINS="floe-core floe-orchestrator-dagster floe-compute-duckdb floe-dbt-core"

# Export transitive closure of all workspace packages with SHA256 hashes.
# --frozen: fail if lockfile is stale (no re-resolution)
# --no-dev: exclude dev dependencies
# --no-editable: produce installable requirements (not editable paths)
# --extra docker: include dagster-webserver/daemon/k8s from orchestrator extras
# NOTE: uv 0.7+ only allows --package once. We use --all-packages to export
# the full workspace closure, then pip install only the target packages.
# --no-emit-workspace should suppress local paths but has a known bug in 0.7.2,
# so we also strip any residual ./path lines that pip cannot resolve.
RUN uv export --frozen --no-dev --no-editable --all-packages --no-emit-workspace --extra docker \
        | grep -v '^\.\/' > requirements.txt

# =============================================================================
# Stage 2: BUILD — Install deps + workspace packages from source
# =============================================================================
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS build

# Build dependencies for C extensions (grpcio, greenlet, pyarrow, duckdb)
# git: required for pip install from git URLs (pyiceberg pinned commit)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc python3-dev libffi-dev git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install all third-party deps from the exported requirements.txt.
# --require-hashes: verify every package against SHA256 hashes from uv export
COPY --from=export /build/requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Copy workspace package source trees (selective per P16 — only installed packages).
# NOTE: This list must include every package that may appear in FLOE_PLUGINS.
# If a new plugin is added to demo/manifest.yaml, add its COPY line here too.
# A missing COPY will cause the build to fail with "ERROR: source for $pkg not found".
COPY packages/floe-core /build/packages/floe-core
COPY plugins/floe-catalog-polaris /build/plugins/floe-catalog-polaris
COPY plugins/floe-orchestrator-dagster /build/plugins/floe-orchestrator-dagster
COPY plugins/floe-compute-duckdb /build/plugins/floe-compute-duckdb
COPY plugins/floe-dbt-core /build/plugins/floe-dbt-core

# Install workspace packages from source (deps already installed above).
# Uses FLOE_PLUGINS ARG to dynamically install only the target packages.
# Re-declare ARG — Docker does not propagate ARGs across stages.
ARG FLOE_PLUGINS="floe-core floe-orchestrator-dagster floe-compute-duckdb floe-dbt-core"
# shellcheck disable=SC2086
RUN set -e; \
    for pkg in $FLOE_PLUGINS; do \
        dir=""; \
        for prefix in /build/packages /build/plugins; do \
            if [ -d "$prefix/$pkg" ]; then dir="$prefix/$pkg"; break; fi; \
        done; \
        if [ -z "$dir" ]; then echo "ERROR: source for $pkg not found" >&2 && exit 1; fi; \
        pip install --no-deps --no-cache-dir "$dir"; \
    done

# Install orchestrator Docker extras not in the uv lockfile.
# dagster-daemon is bundled with core dagster; dagster-k8s uses 0.x versioning
# and is only needed for K8s job execution (not required in-container).
# Versions MUST match uv.lock — update these when bumping dagster in pyproject.toml.
ARG DAGSTER_VERSION=1.12.14
ARG DAGSTER_POSTGRES_VERSION=0.28.14
RUN pip install --no-cache-dir \
        "dagster-webserver==${DAGSTER_VERSION}" \
        "dagster-postgres==${DAGSTER_POSTGRES_VERSION}" \
        "dagster==${DAGSTER_VERSION}" \
        "sqlalchemy>=2.0,<2.1"

# TODO(pyiceberg-0.11.1): Remove git install once PyPI release available
# PyIceberg 0.11.0 rejects Polaris 1.2.0+ PUT in HttpMethod enum.
# Fixed in PR #3010, pinned to merge commit for reproducibility.
# Tracking: https://github.com/apache/iceberg-python/pull/3010
RUN pip install --no-cache-dir \
    "pyiceberg @ git+https://github.com/apache/iceberg-python.git@9687d080f28951464cf02fb2645e2a1185838b21"

# Validate dependency tree is consistent
RUN pip check

# Smoke test: verify core imports resolve and PyIceberg PUT fix present
RUN python -c "import dagster; import floe_core; import dagster_webserver" \
 && python -c "from pyiceberg.catalog.rest import HttpMethod; assert 'PUT' in HttpMethod.__members__"

# =============================================================================
# Stage 3: RUNTIME — Minimal production image
# =============================================================================
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS runtime

# Copy installed packages from build stage (no build tools, no compilers, no uv)
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Demo products (hyphen source dirs → underscore destination for Python imports)
COPY demo/customer-360/ /app/demo/customer_360/
COPY demo/iot-telemetry/ /app/demo/iot_telemetry/
COPY demo/financial-risk/ /app/demo/financial_risk/

# Shared resources
COPY demo/manifest.yaml /app/demo/manifest.yaml
COPY demo/macros/ /app/demo/macros/

# Create __init__.py for Python package discovery.
# Dagster's workingDirectory=/app/demo adds /app/demo to sys.path,
# so each product is discovered as a top-level package (e.g., customer_360)
RUN touch /app/demo/customer_360/__init__.py \
          /app/demo/iot_telemetry/__init__.py \
          /app/demo/financial_risk/__init__.py

# Run as non-root user for reduced attack surface
RUN useradd --create-home --shell /bin/false dagster \
    && mkdir -p /opt/dagster/dagster_home \
    && chown -R dagster:dagster /opt/dagster
USER dagster

ENV DAGSTER_HOME=/opt/dagster/dagster_home

WORKDIR /app/demo
