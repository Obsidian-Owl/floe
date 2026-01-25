# Test runner image for floe K8s-native integration tests
# Build: docker build -t floe-test-runner:latest -f testing/Dockerfile .
# Run: kubectl apply -f testing/k8s/jobs/test-runner.yaml
#
# This image contains:
# - Python 3.11 with uv package manager
# - All floe packages installed
# - pytest and testing dependencies
# - kubectl for K8s operations

FROM python:3.11-slim-bookworm AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install kubectl (enforce HTTPS, TLS 1.2+)
# hadolint ignore=DL3059
RUN KUBECTL_VERSION=$(curl --proto '=https' --tlsv1.2 -fsSL https://dl.k8s.io/release/stable.txt) \
    && curl --proto '=https' --tlsv1.2 -fsSLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# =============================================================================
# dbt Fusion CLI - Install from official distribution
# =============================================================================
# Install the official dbt Fusion CLI from dbt Labs CDN.
# The official CLI supports: compile, run, test, build (full dbt compatibility).
#
# See: https://docs.getdbt.com/docs/fusion/install-fusion-cli

# hadolint ignore=DL3059
RUN curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh | sh -s -- --update \
    && ln -sf /root/.local/bin/dbt /usr/local/bin/dbt

# Verify installation
# hadolint ignore=DL3059
RUN dbt --version

# Set working directory
WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY plugins/ ./plugins/
COPY testing/ ./testing/
COPY tests/ ./tests/

# Create virtual environment and install dependencies
RUN uv sync --frozen

# Create non-root user for security
# hadolint ignore=DL3059
RUN groupadd --gid 1000 floe \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home floe \
    && chown -R floe:floe /app

# Switch to non-root user
USER floe

# Set environment variables
ENV PYTHONPATH=/app:/app/testing
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default test command
ENTRYPOINT ["uv", "run", "pytest"]
CMD ["--tb=short", "-v"]

# Health check (verify pytest is available)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import pytest; print(pytest.__version__)"

# Labels
LABEL org.opencontainers.image.title="floe-test-runner"
LABEL org.opencontainers.image.description="Test runner for floe K8s-native integration tests"
LABEL org.opencontainers.image.source="https://github.com/obsidian-owl/floe"
