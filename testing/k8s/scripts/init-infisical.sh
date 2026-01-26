#!/usr/bin/env bash
# Initialize Infisical for integration testing
# Waits for Infisical to be ready and checks API status
#
# Usage: ./testing/k8s/scripts/init-infisical.sh
#
# Environment variables:
#   INFISICAL_URL: Infisical base URL (default: http://localhost:8083)
#   MAX_ATTEMPTS: Number of health check attempts (default: 60)
#   SLEEP_SECONDS: Wait between attempts (default: 5)
#
# Note: First-run setup creates admin user automatically via the UI.
# For automated testing, use Universal Auth credentials configured
# in the test fixtures.

set -euo pipefail

INFISICAL_URL="${INFISICAL_URL:-http://localhost:8083}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-60}"
SLEEP_SECONDS="${SLEEP_SECONDS:-5}"

echo "Waiting for Infisical to be ready at ${INFISICAL_URL}..."

for i in $(seq 1 "${MAX_ATTEMPTS}"); do
    # Check API status endpoint
    if curl -sf "${INFISICAL_URL}/api/status" > /dev/null 2>&1; then
        echo "Infisical is ready!"
        echo ""
        echo "Infisical Test Configuration:"
        echo "  URL: ${INFISICAL_URL}"
        echo ""
        echo "Note: First-time setup requires manual configuration via UI."
        echo "For integration tests, Universal Auth credentials are provided"
        echo "via environment variables in the test fixtures."
        echo ""
        exit 0
    fi

    echo "  Attempt ${i}/${MAX_ATTEMPTS}..."
    sleep "${SLEEP_SECONDS}"
done

echo "ERROR: Infisical did not become ready within ${MAX_ATTEMPTS} attempts" >&2
exit 1
