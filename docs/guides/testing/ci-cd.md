# CI/CD Pipeline

This guide covers the GitHub Actions CI/CD configuration for floe.

---

## GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: uv pip install ruff mypy

      - name: Lint with ruff
        run: ruff check .

      - name: Type check with mypy
        run: mypy floe_core floe_cli floe_dagster floe_dbt

  test-unit:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Run unit tests
        run: uv run pytest tests/unit -v --cov=floe_core --cov=floe_cli --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: coverage.xml

  test-integration:
    runs-on: ubuntu-latest
    needs: [lint, test-unit]
    steps:
      - uses: actions/checkout@v4

      - name: Create Kind cluster
        uses: helm/kind-action@v1
        with:
          cluster_name: floe-test

      - name: Install Helm
        uses: azure/setup-helm@v4

      - name: Build test runner image
        run: |
          docker build -t floe-test-runner:local -f tests/Dockerfile .
          kind load docker-image floe-test-runner:local --name floe-test

      - name: Deploy floe-platform (minimal)
        run: |
          helm install floe-test ./charts/floe-platform \
            --namespace floe-test --create-namespace \
            --set dagster.enabled=true \
            --set polaris.enabled=false \
            --set cube.enabled=false \
            --wait --timeout=5m

      - name: Run integration tests in K8s
        run: |
          kubectl apply -f tests/integration/test-job.yaml -n floe-test
          kubectl wait --for=condition=complete job/integration-tests -n floe-test --timeout=5m

      - name: Collect test results
        if: always()
        run: |
          kubectl logs job/integration-tests -n floe-test > test-results.log
          kubectl cp floe-test/integration-tests:/results/junit.xml ./junit-integration.xml || true

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: integration-test-results
          path: |
            test-results.log
            junit-integration.xml

  test-e2e:
    runs-on: ubuntu-latest
    needs: [test-integration]
    steps:
      - uses: actions/checkout@v4

      - name: Create Kind cluster
        uses: helm/kind-action@v1
        with:
          cluster_name: floe-e2e
          config: tests/e2e/kind-config.yaml  # Multi-node for realism

      - name: Install Helm
        uses: azure/setup-helm@v4

      - name: Build all images
        run: |
          docker build -t floe/dagster:local -f docker/dagster/Dockerfile .
          docker build -t floe/test-runner:local -f tests/Dockerfile .
          kind load docker-image floe/dagster:local --name floe-e2e
          kind load docker-image floe/test-runner:local --name floe-e2e

      - name: Deploy floe-platform (FULL stack)
        run: |
          # Deploy full production-like stack
          helm install floe-e2e ./charts/floe-platform \
            --namespace floe-e2e --create-namespace \
            --set dagster.enabled=true \
            --set polaris.enabled=true \
            --set cube.enabled=true \
            --set observability.enabled=true \
            --wait --timeout=10m

      - name: Run E2E tests in K8s
        run: |
          kubectl apply -f tests/e2e/test-job.yaml -n floe-e2e
          kubectl wait --for=condition=complete job/e2e-tests -n floe-e2e --timeout=10m

      - name: Collect test results
        if: always()
        run: |
          kubectl logs job/e2e-tests -n floe-e2e > e2e-results.log
          kubectl cp floe-e2e/e2e-tests:/results/junit.xml ./junit-e2e.xml || true

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: e2e-test-results
          path: |
            e2e-results.log
            junit-e2e.xml

  build-container:
    runs-on: ubuntu-latest
    needs: [test-unit]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build container
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: floe/dagster:test
          cache-from: type=gha
          cache-to: type=gha,mode=max

  test-platforms:
    runs-on: ${{ matrix.os }}
    needs: [lint]
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.11"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install and test CLI
        run: |
          uv sync
          uv run floe --version
          uv run floe --help
```

---

## Release Workflow

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build packages
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}

  build-and-push-container:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64
          tags: |
            ghcr.io/floe/dagster:${{ github.ref_name }}
            ghcr.io/floe/dagster:latest
```

---

## Related

- [Testing Index](index.md)
- [K8s Testing Infrastructure](k8s-infrastructure.md)
- [Code Quality](code-quality.md)
