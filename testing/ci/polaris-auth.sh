#!/bin/bash
# Polaris OAuth2 token acquisition helper
#
# Provides reusable functions for Polaris API authentication.
# Sourced by wait-for-services.sh and other CI scripts.
#
# Usage:
#   source testing/ci/polaris-auth.sh
#   TOKEN=$(get_polaris_token "http://localhost:8181")
#
# Environment:
#   POLARIS_CLIENT_ID     Client ID (default: from MANIFEST_OAUTH_CLIENT_ID)
#   POLARIS_CLIENT_SECRET Client secret (required — no hardcoded default)

# Acquire an OAuth2 bearer token from the Polaris catalog API.
#
# Args:
#   $1 - Polaris base URL (e.g., http://localhost:8181)
#
# Outputs:
#   Writes the access token to stdout.
#   Writes errors to stderr.
#
# Returns:
#   0 on success, 1 on failure.
get_polaris_token() {
    local polaris_url="${1:?Usage: get_polaris_token <polaris_url>}"
    local client_id="${POLARIS_CLIENT_ID:-${MANIFEST_OAUTH_CLIENT_ID:-}}"
    local client_secret="${POLARIS_CLIENT_SECRET:-}"

    if [[ -z "$client_id" ]]; then
        echo "ERROR: POLARIS_CLIENT_ID not set (source extract-manifest-config.py first)" >&2
        return 1
    fi
    if [[ -z "$client_secret" ]]; then
        echo "ERROR: POLARIS_CLIENT_SECRET not set" >&2
        return 1
    fi

    local token
    # Pipe credentials via stdin (-d @-) to avoid exposing them in
    # process arguments (visible in ps aux / /proc/*/cmdline).
    token=$(printf 'grant_type=client_credentials&client_id=%s&client_secret=%s&scope=PRINCIPAL_ROLE:ALL' \
        "$client_id" "$client_secret" | \
        curl -sf -X POST \
        "$polaris_url/api/catalog/v1/oauth/tokens" \
        -d @- \
        2>/dev/null | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

    if [[ -z "$token" ]]; then
        echo "ERROR: Failed to acquire Polaris OAuth token from $polaris_url" >&2
        return 1
    fi

    echo "$token"
}

# Verify a Polaris catalog exists via the management API.
#
# Args:
#   $1 - Polaris base URL (e.g., http://localhost:8181)
#   $2 - Catalog name (e.g., floe-e2e)
#   $3 - Bearer token
#
# Returns:
#   0 if catalog exists, 1 otherwise.
verify_polaris_catalog() {
    local polaris_url="${1:?Usage: verify_polaris_catalog <polaris_url> <catalog_name> <token>}"
    local catalog_name="${2:?Usage: verify_polaris_catalog <polaris_url> <catalog_name> <token>}"
    local token="${3:?Usage: verify_polaris_catalog <polaris_url> <catalog_name> <token>}"

    # Validate catalog name to prevent URL injection (alphanumeric, hyphens, underscores only)
    if [[ ! "$catalog_name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "ERROR: Invalid catalog name: '$catalog_name' (must be alphanumeric, hyphens, underscores)" >&2
        return 1
    fi

    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        -H "Authorization: Bearer $token" \
        "$polaris_url/api/management/v1/catalogs/$catalog_name" 2>/dev/null)

    if [[ "$http_code" == "200" ]]; then
        return 0
    else
        echo "ERROR: Catalog '$catalog_name' not found (HTTP $http_code)" >&2
        return 1
    fi
}
