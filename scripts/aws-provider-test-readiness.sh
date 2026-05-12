#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-readiness] $*" >&2
}

error() {
    echo "[aws-provider-readiness] ERROR: $*" >&2
    exit 1
}

require_env() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        error "${name} is required"
    fi
}

require_env FLOE_AWS_REGION
require_env FLOE_AWS_TEST_BUCKET
require_env FLOE_AWS_GLUE_DATABASE_PREFIX

test_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}"

validate_inputs() {
    if [[ ! "${test_prefix}" =~ ^runs/$ ]]; then
        error "FLOE_AWS_TEST_PREFIX must match ^runs/$ for first live validation"
    fi

    if [[ ! "${FLOE_AWS_GLUE_DATABASE_PREFIX}" =~ ^floe_provider_$ ]]; then
        error "FLOE_AWS_GLUE_DATABASE_PREFIX must match ^floe_provider_$ for first live validation"
    fi
}

validate_inputs

aws_args=(--region "${FLOE_AWS_REGION}")
database_payload="$(mktemp)"

log "Checking AWS caller identity"
aws sts get-caller-identity "${aws_args[@]}"

log "Checking S3 bucket access: ${FLOE_AWS_TEST_BUCKET}"
aws s3api get-bucket-location \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    "${aws_args[@]}"

log "Checking S3 list access"
aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${test_prefix}" \
    --max-items 1 \
    "${aws_args[@]}" >/dev/null

probe_db="${FLOE_AWS_GLUE_DATABASE_PREFIX}readiness_$(date -u +%Y%m%d%H%M%S)"

cleanup_probe() {
    rm -f "${database_payload}"
    aws glue delete-database \
        --database-name "${probe_db}" \
        "${aws_args[@]}" >/dev/null 2>&1 || true
}
trap cleanup_probe EXIT

log "Checking Glue create/get/delete access with ${probe_db}"
printf '{"Name":"%s"}\n' "${probe_db}" >"${database_payload}"
aws glue create-database \
    --database-input "file://${database_payload}" \
    "${aws_args[@]}" >/dev/null
aws glue get-database \
    --name "${probe_db}" \
    "${aws_args[@]}" >/dev/null
aws glue delete-database \
    --database-name "${probe_db}" \
    "${aws_args[@]}" >/dev/null

log "Readiness checks passed"
