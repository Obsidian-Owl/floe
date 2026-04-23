#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"
mkdir -p test-artifacts

uv run pytest tests/e2e \
  -m "bootstrap" \
  --tb=short \
  -v \
  --junitxml=test-artifacts/bootstrap-results.xml
