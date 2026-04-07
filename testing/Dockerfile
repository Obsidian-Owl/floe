# Test runner image for floe K8s-native integration tests
# Build: docker build -t floe-test-runner:latest -f testing/Dockerfile .
# Run: testing/ci/test-e2e-cluster.sh (renders Job from charts/floe-platform)
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

# Install uv for fast package management (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv

# Install kubectl (enforce HTTPS, TLS 1.2+, checksum verification)
# hadolint ignore=DL3059
RUN KUBECTL_VERSION=$(curl --proto '=https' --tlsv1.2 -fsSL https://dl.k8s.io/release/stable.txt) \
    && curl --proto '=https' --tlsv1.2 -fsSLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && curl --proto '=https' --tlsv1.2 -fsSLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl.sha256" \
    && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check \
    && rm kubectl.sha256 \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Helm 4 CLI (needed by destructive E2E tests that run helm upgrade)
# hadolint ignore=DL3059
RUN curl --proto '=https' --tlsv1.2 -fsSLO https://get.helm.sh/helm-v4.1.3-linux-amd64.tar.gz \
    && curl --proto '=https' --tlsv1.2 -fsSLO https://get.helm.sh/helm-v4.1.3-linux-amd64.tar.gz.sha256sum \
    && sha256sum --check helm-v4.1.3-linux-amd64.tar.gz.sha256sum \
    && tar xz --strip-components=1 -C /usr/local/bin linux-amd64/helm < helm-v4.1.3-linux-amd64.tar.gz \
    && rm helm-v4.1.3-linux-amd64.tar.gz helm-v4.1.3-linux-amd64.tar.gz.sha256sum \
    && helm version --short

# =============================================================================
# dbt Fusion CLI - Install from official distribution
# =============================================================================
# Install the official dbt Fusion CLI from dbt Labs CDN.
# The official CLI supports: compile, run, test, build (full dbt compatibility).
#
# See: https://docs.getdbt.com/docs/fusion/install-fusion-cli

# Download first, then execute (CWE-78 mitigation — no pipe-to-shell)
# SHELL env var required by dbt Fusion install script (not set in Docker /bin/sh)
ENV SHELL=/bin/bash
# hadolint ignore=DL3059
RUN curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh -o /tmp/dbt-install.sh \
    && chmod +x /tmp/dbt-install.sh \
    && /tmp/dbt-install.sh --update \
    && rm -f /tmp/dbt-install.sh \
    && cp /root/.local/bin/dbt /usr/local/bin/dbt \
    && chmod a+rx /usr/local/bin/dbt \
    && dbt --version

# Set working directory
WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY plugins/ ./plugins/
COPY testing/ ./testing/
COPY tests/ ./tests/
COPY demo/ ./demo/
COPY charts/ ./charts/

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
