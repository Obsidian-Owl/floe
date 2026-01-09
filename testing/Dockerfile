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

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY testing/ ./testing/
COPY tests/ ./tests/

# Create virtual environment and install dependencies
RUN uv sync --frozen

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
