#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-readiness] $*" >&2
}

require_env() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        echo "[aws-provider-readiness] ERROR: ${name} is required" >&2
        exit 1
    fi
}

require_env FLOE_AWS_REGION
require_env FLOE_AWS_TEST_BUCKET
require_env FLOE_AWS_GLUE_DATABASE_PREFIX

aws_args=(--region "${FLOE_AWS_REGION}")

log "Checking AWS caller identity"
aws sts get-caller-identity "${aws_args[@]}"

log "Checking S3 bucket access: ${FLOE_AWS_TEST_BUCKET}"
aws s3api get-bucket-location \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    "${aws_args[@]}"

log "Checking S3 list access"
aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${FLOE_AWS_TEST_PREFIX:-runs/}" \
    --max-items 1 \
    "${aws_args[@]}" >/dev/null

probe_db="${FLOE_AWS_GLUE_DATABASE_PREFIX}readiness_$(date -u +%Y%m%d%H%M%S)"

cleanup_probe() {
    aws glue delete-database \
        --database-name "${probe_db}" \
        "${aws_args[@]}" >/dev/null 2>&1 || true
}
trap cleanup_probe EXIT

log "Checking Glue create/get/delete access with ${probe_db}"
aws glue create-database \
    --database-input "{\"Name\":\"${probe_db}\"}" \
    "${aws_args[@]}" >/dev/null
aws glue get-database \
    --name "${probe_db}" \
    "${aws_args[@]}" >/dev/null
aws glue delete-database \
    --database-name "${probe_db}" \
    "${aws_args[@]}" >/dev/null

log "Readiness checks passed"
