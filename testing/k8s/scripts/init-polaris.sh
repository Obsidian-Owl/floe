#!/usr/bin/env bash
# Initialize Polaris catalog for testing
# Creates the test_warehouse catalog used by integration tests
#
# Prerequisites:
#   - Polaris service is running and accessible at localhost:8181
#   - Bootstrap credentials are set via POLARIS_BOOTSTRAP_CREDENTIALS
#
# This script:
#   1. Authenticates with Polaris using test credentials
#   2. Creates the test_warehouse catalog pointing to MinIO

set -euo pipefail

POLARIS_HOST="${POLARIS_HOST:-localhost}"
POLARIS_PORT="${POLARIS_PORT:-8181}"
POLARIS_URL="http://${POLARIS_HOST}:${POLARIS_PORT}"

# Test credentials (must match POLARIS_BOOTSTRAP_CREDENTIALS in polaris.yaml)
CLIENT_ID="${POLARIS_CLIENT_ID:-test-admin}"
CLIENT_SECRET="${POLARIS_CLIENT_SECRET:-test-secret}"

# MinIO configuration
MINIO_HOST="${MINIO_HOST:-minio}"
MINIO_PORT="${MINIO_PORT:-9000}"
S3_ENDPOINT="http://${MINIO_HOST}:${MINIO_PORT}"

# Catalog name
CATALOG_NAME="${POLARIS_WAREHOUSE:-test_warehouse}"

log_info() {
    echo "[INFO] $1" >&2
}

log_error() {
    echo "[ERROR] $1" >&2
}

# Get OAuth2 token
get_token() {
    log_info "Authenticating with Polaris..."

    local response
    response=$(curl -s -X POST "${POLARIS_URL}/api/catalog/v1/oauth/tokens" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=client_credentials" \
        -d "client_id=${CLIENT_ID}" \
        -d "client_secret=${CLIENT_SECRET}" \
        -d "scope=PRINCIPAL_ROLE:ALL")

    # Extract access token
    local token
    token=$(echo "$response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

    if [[ -z "$token" ]]; then
        log_error "Failed to get access token. Response: $response"
        exit 1
    fi

    echo "$token"
}

# Check if catalog exists
catalog_exists() {
    local token=$1
    local catalog_name=$2

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${token}" \
        "${POLARIS_URL}/api/management/v1/catalogs/${catalog_name}")

    [[ "$status" == "200" ]]
}

# Create catalog
create_catalog() {
    local token=$1
    local catalog_name=$2

    log_info "Creating catalog: ${catalog_name}..."

    # MinIO-compatible storageConfigInfo for Polaris 1.1.0+
    # Note: roleArn is NOT needed for MinIO (unlike AWS S3)
    # - endpoint: client-facing URL (Kind NodePort access from host)
    # - endpointInternal: server-side URL (K8s internal DNS for Polaris)
    # - pathStyleAccess: required for MinIO
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${POLARIS_URL}/api/management/v1/catalogs" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"catalog\": {
                \"name\": \"${catalog_name}\",
                \"type\": \"INTERNAL\",
                \"properties\": {
                    \"default-base-location\": \"s3://floe-warehouse/${catalog_name}\",
                    \"polaris.config.drop-with-purge.enabled\": \"true\"
                },
                \"storageConfigInfo\": {
                    \"storageType\": \"S3\",
                    \"allowedLocations\": [\"s3://floe-warehouse/\"],
                    \"endpoint\": \"http://localhost:9000\",
                    \"endpointInternal\": \"http://minio:9000\",
                    \"pathStyleAccess\": true
                }
            }
        }")

    # Check if creation was successful (201 = created)
    if [[ "$status" == "201" ]]; then
        log_info "Catalog ${catalog_name} created successfully"
    elif [[ "$status" == "409" ]]; then
        log_info "Catalog ${catalog_name} already exists (409 Conflict)"
    else
        log_error "Failed to create catalog. HTTP status: $status"
    fi
}

# Create catalog role with table operation privileges
setup_catalog_role() {
    local token=$1
    local catalog_name=$2
    local role_name="test_data_admin"

    log_info "Creating catalog role: ${role_name}..."

    # Create catalog role
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "${POLARIS_URL}/api/management/v1/catalogs/${catalog_name}/catalog-roles" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"catalogRole\": {\"name\": \"${role_name}\"}}")

    if [[ "$status" == "201" || "$status" == "409" ]]; then
        log_info "Catalog role ${role_name} created (or exists)"
    else
        log_error "Failed to create catalog role. HTTP status: $status"
        return
    fi

    # Grant privileges for table operations
    local privileges=(
        "CATALOG_MANAGE_CONTENT"
        "TABLE_CREATE"
        "TABLE_DROP"
        "TABLE_READ_DATA"
        "TABLE_WRITE_DATA"
        "TABLE_LIST"
        "NAMESPACE_CREATE"
        "NAMESPACE_DROP"
        "NAMESPACE_LIST"
    )

    for priv in "${privileges[@]}"; do
        curl -s -o /dev/null -X PUT \
            "${POLARIS_URL}/api/management/v1/catalogs/${catalog_name}/catalog-roles/${role_name}/grants" \
            -H "Authorization: Bearer ${token}" \
            -H "Content-Type: application/json" \
            -d "{\"grant\": {\"type\": \"catalog\", \"privilege\": \"${priv}\"}}"
    done

    log_info "Privileges granted to ${role_name}"

    # Assign catalog role to service_admin principal role
    status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
        "${POLARIS_URL}/api/management/v1/principal-roles/service_admin/catalog-roles/${catalog_name}" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"catalogRole\": {\"name\": \"${role_name}\"}}")

    if [[ "$status" == "201" || "$status" == "200" || "$status" == "204" ]]; then
        log_info "Catalog role ${role_name} assigned to service_admin"
    else
        log_error "Failed to assign catalog role. HTTP status: $status"
    fi
}

# Main
main() {
    log_info "Initializing Polaris catalog..."

    # Wait for Polaris to be ready
    log_info "Waiting for Polaris at ${POLARIS_URL}..."
    local max_attempts=30
    local attempt=0
    while ! curl -s "${POLARIS_URL}/healthcheck" > /dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            log_error "Polaris not ready after ${max_attempts} attempts"
            exit 1
        fi
        sleep 2
    done
    log_info "Polaris is ready"

    # Get authentication token
    local token
    token=$(get_token)
    log_info "Authentication successful"

    # Check if catalog already exists
    if catalog_exists "$token" "$CATALOG_NAME"; then
        log_info "Catalog ${CATALOG_NAME} already exists"
    else
        create_catalog "$token" "$CATALOG_NAME"
    fi

    # Setup catalog role with table privileges
    setup_catalog_role "$token" "$CATALOG_NAME"

    log_info "Polaris initialization complete"
}

main "$@"
