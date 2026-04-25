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
#   POLARIS_CLIENT_SECRET Client secret (default: from FLOE_MANIFEST_PATH)
#   POLARIS_SCOPE         OAuth scope (default: from MANIFEST_OAUTH_SCOPE or manifest)
#   FLOE_MANIFEST_PATH    Canonical manifest path override
#   POLARIS_MANIFEST_PATH Back-compat manifest path override

_polaris_manifest_path() {
    if [[ -n "${FLOE_MANIFEST_PATH:-}" ]]; then
        printf '%s\n' "${FLOE_MANIFEST_PATH}"
        return 0
    fi

    if [[ -n "${POLARIS_MANIFEST_PATH:-}" ]]; then
        printf '%s\n' "${POLARIS_MANIFEST_PATH}"
        return 0
    fi

    local script_dir repo_root
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(cd "${script_dir}/../.." && pwd)"
    printf '%s\n' "${repo_root}/demo/manifest.yaml"
}

_manifest_polaris_field() {
    local field="${1:?Usage: _manifest_polaris_field <field>}"
    local manifest_path
    manifest_path="$(_polaris_manifest_path)"

    if [[ ! -f "${manifest_path}" ]]; then
        return 0
    fi

    python3 - "${manifest_path}" "${field}" <<'PY'
from pathlib import Path
import sys

import yaml

manifest_path = Path(sys.argv[1])
field = sys.argv[2]

try:
    raw = yaml.safe_load(manifest_path.read_text()) or {}
except Exception:
    print("", end="")
    raise SystemExit(0)

catalog = raw.get("plugins", {}).get("catalog", {}).get("config", {})
oauth2 = catalog.get("oauth2", {})

value = ""
if field == "client_secret":
    value = oauth2.get("client_secret", "")
elif field == "scope":
    value = catalog.get("scope", oauth2.get("scope", ""))
elif field == "warehouse":
    value = catalog.get("warehouse", "")

print("" if value is None else str(value), end="")
PY
}

get_polaris_scope() {
    local scope="${POLARIS_SCOPE:-${MANIFEST_OAUTH_SCOPE:-$(_manifest_polaris_field scope)}}"
    if [[ -z "${scope}" ]]; then
        echo "ERROR: POLARIS_SCOPE not set and manifest does not provide oauth2.scope" >&2
        return 1
    fi
    echo "${scope}"
}

get_polaris_catalog_name() {
    local catalog_name="${POLARIS_CATALOG_NAME:-${POLARIS_CATALOG:-${MANIFEST_WAREHOUSE:-$(_manifest_polaris_field warehouse)}}}"
    if [[ -z "${catalog_name}" ]]; then
        echo "ERROR: Polaris catalog name not set and manifest does not provide catalog.config.warehouse" >&2
        return 1
    fi
    echo "${catalog_name}"
}

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
    local client_secret="${POLARIS_CLIENT_SECRET:-$(_manifest_polaris_field client_secret)}"
    local scope
    scope="$(get_polaris_scope)" || return 1

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
    token=$(printf 'grant_type=client_credentials&client_id=%s&client_secret=%s&scope=%s' \
        "$client_id" "$client_secret" "$scope" | \
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
#   $2 - Catalog name (e.g., floe-demo)
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
