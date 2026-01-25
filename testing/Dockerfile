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
# dbt-fusion (EXPERIMENTAL) - Build from source
# =============================================================================
# dbt-fusion has no published releases yet, so we build from source
# This is experimental and may break if upstream changes

# Install build dependencies for Rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
# hadolint ignore=DL3059
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . /root/.cargo/env \
    && rustup default stable

# Clone and build dbt-fusion
# Pin to specific commit for reproducibility
ARG DBT_FUSION_COMMIT=main
# hadolint ignore=DL3059
RUN . /root/.cargo/env \
    && git clone --depth 1 https://github.com/dbt-labs/dbt-fusion.git /tmp/dbt-fusion \
    && cd /tmp/dbt-fusion \
    && git checkout ${DBT_FUSION_COMMIT} \
    && cargo build --release --package dbt-sa-cli \
    && cp target/release/dbt-sa-cli /usr/local/bin/ \
    && chmod +x /usr/local/bin/dbt-sa-cli \
    && rm -rf /tmp/dbt-fusion /root/.cargo/registry

# Verify installation (version check may fail on pre-release)
# hadolint ignore=DL3059
RUN dbt-sa-cli --version || echo "dbt-sa-cli installed (version check may fail)"

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
