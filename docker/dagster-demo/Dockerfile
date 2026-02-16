# Dagster Demo Image
# ==================
#
# Custom Dagster image with demo product code baked in.
# Extends the stock Dagster Celery+K8s image with:
#   - floe packages (floe-core, orchestrator, compute, dbt plugins)
#   - Demo products (customer-360, iot-telemetry, financial-risk)
#   - dbt compiled manifests (target/manifest.json per product)
#
# Build:
#   docker build -f docker/dagster-demo/Dockerfile -t floe-dagster-demo:latest .
#
# Requirements:
#   - Run `make compile-demo` before building (generates target/manifest.json)
#   - Build context must be the repo root

FROM dagster/dagster-celery-k8s:1.9.6

# Install floe packages needed by generated definitions.py
# Use --no-deps to avoid conflicts with pre-installed dagster packages
# Copy only the specific packages installed below (not the entire directories)
COPY packages/floe-core /build/packages/floe-core
COPY plugins/floe-orchestrator-dagster /build/plugins/floe-orchestrator-dagster
COPY plugins/floe-compute-duckdb /build/plugins/floe-compute-duckdb
COPY plugins/floe-dbt-core /build/plugins/floe-dbt-core
RUN pip install --no-deps \
        /build/packages/floe-core \
        /build/plugins/floe-orchestrator-dagster \
        /build/plugins/floe-compute-duckdb \
        /build/plugins/floe-dbt-core \
    && pip check \
    && rm -rf /build

# Copy demo products with Python-compatible directory names
# Source directories use hyphens (dbt convention), destinations use underscores (Python convention)
COPY demo/customer-360/ /app/demo/customer_360/
COPY demo/iot-telemetry/ /app/demo/iot_telemetry/
COPY demo/financial-risk/ /app/demo/financial_risk/

# Copy shared resources
COPY demo/manifest.yaml /app/demo/manifest.yaml
COPY demo/macros/ /app/demo/macros/

# Create __init__.py for Python package discovery
# Dagster's workingDirectory=/app/demo adds /app/demo to sys.path,
# so each product is discovered as a top-level package (e.g., customer_360)
RUN touch /app/demo/customer_360/__init__.py \
          /app/demo/iot_telemetry/__init__.py \
          /app/demo/financial_risk/__init__.py

WORKDIR /app/demo
