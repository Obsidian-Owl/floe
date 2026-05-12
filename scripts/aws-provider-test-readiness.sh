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
require_env FLOE_AWS_BUDGET_NAME
require_env FLOE_AWS_PROVIDER_TEST_POLICY_ARN

test_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}"

validate_inputs() {
    if [[ ! "${test_prefix}" =~ ^[a-zA-Z0-9][a-zA-Z0-9/_-]*/$ ]]; then
        error "FLOE_AWS_TEST_PREFIX must be a relative S3 prefix ending with /"
    fi

    if [[ "${test_prefix}" == "/" || "${test_prefix}" == "../"* || "${test_prefix}" == *"/../"* ]]; then
        error "FLOE_AWS_TEST_PREFIX must not be root or contain parent traversal"
    fi

    if [[ ! "${FLOE_AWS_GLUE_DATABASE_PREFIX}" =~ ^[a-z][a-z0-9_]{2,40}_$ ]]; then
        error "FLOE_AWS_GLUE_DATABASE_PREFIX must be lowercase snake_case and end with _"
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

log "Checking S3 public access block"
public_access_state="$(
    aws s3api get-public-access-block \
        --bucket "${FLOE_AWS_TEST_BUCKET}" \
        --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,IgnorePublicAcls,BlockPublicPolicy,RestrictPublicBuckets]' \
        --output text \
        "${aws_args[@]}"
)"
if [[ "${public_access_state}" != $'True\tTrue\tTrue\tTrue' ]]; then
    error "S3 public access block is not fully enabled for ${FLOE_AWS_TEST_BUCKET}: ${public_access_state}"
fi

log "Checking S3 lifecycle rule for ${test_prefix}"
lifecycle_rule_count="$(
    aws s3api get-bucket-lifecycle-configuration \
        --bucket "${FLOE_AWS_TEST_BUCKET}" \
        --query "length(Rules[?Status == 'Enabled' && Filter.Prefix == '${test_prefix}'])" \
        --output text \
        "${aws_args[@]}"
)"
if [[ "${lifecycle_rule_count}" == "0" ]]; then
    error "No enabled S3 lifecycle rule found for prefix ${test_prefix}"
fi

log "Checking AWS Budget: ${FLOE_AWS_BUDGET_NAME}"
account_id="$(
    aws sts get-caller-identity \
        --query Account \
        --output text \
        "${aws_args[@]}"
)"
aws budgets describe-budget \
    --account-id "${account_id}" \
    --budget-name "${FLOE_AWS_BUDGET_NAME}" >/dev/null

log "Checking provider test IAM policy: ${FLOE_AWS_PROVIDER_TEST_POLICY_ARN}"
aws iam get-policy \
    --policy-arn "${FLOE_AWS_PROVIDER_TEST_POLICY_ARN}" >/dev/null

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
