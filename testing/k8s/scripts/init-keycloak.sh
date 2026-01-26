#!/usr/bin/env bash
# Initialize Keycloak for integration testing
# Waits for Keycloak to be ready (realm import happens on startup)
#
# Usage: ./testing/k8s/scripts/init-keycloak.sh
#
# Environment variables:
#   KEYCLOAK_URL: Keycloak base URL (default: http://localhost:8082)
#   MAX_ATTEMPTS: Number of health check attempts (default: 60)
#   SLEEP_SECONDS: Wait between attempts (default: 5)

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8082}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-60}"
SLEEP_SECONDS="${SLEEP_SECONDS:-5}"

echo "Waiting for Keycloak to be ready at ${KEYCLOAK_URL}..."

for i in $(seq 1 "${MAX_ATTEMPTS}"); do
    if curl -sf "${KEYCLOAK_URL}/health/ready" > /dev/null 2>&1; then
        echo "Keycloak is ready!"

        # Verify floe realm was imported
        if curl -sf "${KEYCLOAK_URL}/realms/floe/.well-known/openid-configuration" > /dev/null 2>&1; then
            echo "Floe realm is available"
            echo ""
            echo "Keycloak Test Credentials:"
            echo "  Admin Console: ${KEYCLOAK_URL}"
            echo "  Admin User:    admin / admin-secret-123"
            echo ""
            echo "  Test Client:   floe-client / floe-client-secret"
            echo "  Test User:     testuser / testuser-password"
            echo "  Admin User:    admin / admin-password"
            echo ""
            exit 0
        else
            echo "Warning: Floe realm not yet available, waiting..."
        fi
    fi

    echo "  Attempt ${i}/${MAX_ATTEMPTS}..."
    sleep "${SLEEP_SECONDS}"
done

echo "ERROR: Keycloak did not become ready within ${MAX_ATTEMPTS} attempts" >&2
exit 1
