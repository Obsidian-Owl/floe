#!/bin/bash
# Fast host-side unit gate for Specwright build/verify.
#
# The repository-wide `make test-unit` suite no longer fits Specwright's
# five-minute build-gate budget. This command keeps a deterministic,
# sub-minute host-side check over the shared chart/test-harness surface that
# Specwright units in this repo currently change most often.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

uv run pytest -q \
    testing/tests/unit/test_polaris_fixture.py \
    testing/tests/unit/test_ci_workflows.py \
    testing/tests/unit/test_pvc_ownership_contract.py \
    testing/tests/unit/test_pvc_runner_contract.py \
    tests/unit/test_helm_bootstrap_template.py \
    tests/unit/test_helm_values_rbac.py \
    "$@"
