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
require_env FLOE_AWS_BUDGET_EMAIL
require_env FLOE_AWS_PROVIDER_TEST_POLICY_ARN

test_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}"

require_command() {
    local name="$1"
    if ! command -v "${name}" >/dev/null 2>&1; then
        error "${name} is required"
    fi
}

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
require_command jq

aws_args=(--region "${FLOE_AWS_REGION}")
database_payload="$(mktemp)"
budget_notifications_payload="$(mktemp)"
budget_subscribers_payload="$(mktemp)"
policy_payload="$(mktemp)"
probe_db=""

cleanup_probe() {
    rm -f "${database_payload}" "${budget_notifications_payload}" "${budget_subscribers_payload}" "${policy_payload}"
    if [[ -n "${probe_db}" ]]; then
        aws glue delete-database \
            --name "${probe_db}" \
            "${aws_args[@]}" >/dev/null 2>&1 || true
    fi
}
trap cleanup_probe EXIT

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
aws budgets describe-notifications-for-budget \
    --account-id "${account_id}" \
    --budget-name "${FLOE_AWS_BUDGET_NAME}" >"${budget_notifications_payload}"
jq -e '
  .Notifications
  | any(.NotificationType == "ACTUAL"
      and .ComparisonOperator == "GREATER_THAN"
      and .Threshold == 80
      and ((.ThresholdType // "PERCENTAGE") == "PERCENTAGE"))
    and any(.NotificationType == "FORECASTED"
      and .ComparisonOperator == "GREATER_THAN"
      and .Threshold == 100
      and ((.ThresholdType // "PERCENTAGE") == "PERCENTAGE"))
' "${budget_notifications_payload}" >/dev/null || \
    error "AWS Budget ${FLOE_AWS_BUDGET_NAME} is missing expected 80% actual or 100% forecasted notifications"

for notification in \
    '{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE"}' \
    '{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"}'; do
    aws budgets describe-subscribers-for-notification \
        --account-id "${account_id}" \
        --budget-name "${FLOE_AWS_BUDGET_NAME}" \
        --notification "${notification}" >"${budget_subscribers_payload}"
    jq -e --arg email "${FLOE_AWS_BUDGET_EMAIL}" '
      .Subscribers
      | any(.SubscriptionType == "EMAIL" and .Address == $email)
    ' "${budget_subscribers_payload}" >/dev/null || \
        error "AWS Budget ${FLOE_AWS_BUDGET_NAME} notification is missing subscriber ${FLOE_AWS_BUDGET_EMAIL}"
done

log "Checking provider test IAM policy: ${FLOE_AWS_PROVIDER_TEST_POLICY_ARN}"
policy_version="$(
    aws iam get-policy \
        --policy-arn "${FLOE_AWS_PROVIDER_TEST_POLICY_ARN}" \
        --query 'Policy.DefaultVersionId' \
        --output text
)"
aws iam get-policy-version \
    --policy-arn "${FLOE_AWS_PROVIDER_TEST_POLICY_ARN}" \
    --version-id "${policy_version}" \
    --query 'PolicyVersion.Document' \
    --output json >"${policy_payload}"
jq -e \
    --arg bucket "arn:aws:s3:::${FLOE_AWS_TEST_BUCKET}" \
    --arg objects "arn:aws:s3:::${FLOE_AWS_TEST_BUCKET}/${test_prefix}*" \
    --arg region "${FLOE_AWS_REGION}" \
    --arg account "${account_id}" \
    --arg glue_prefix "${FLOE_AWS_GLUE_DATABASE_PREFIX}" '
  def stmts: .Statement | if type == "array" then . else [.] end;
  def actions($s): ($s.Action | if type == "array" then . else [.] end);
  def resources($s): ($s.Resource | if type == "array" then . else [.] end);
  any(stmts[]; (actions(.) | index("s3:ListBucket")) and (resources(.) | index($bucket)))
  and any(stmts[]; (actions(.) | index("s3:PutObject")) and (actions(.) | index("s3:DeleteObject")) and (resources(.) | index($objects)))
  and any(stmts[]; (actions(.) | index("glue:CreateDatabase")) and (resources(.) | index("arn:aws:glue:\($region):\($account):database/\($glue_prefix)*")))
  and any(stmts[]; (actions(.) | index("glue:CreateTable")) and (resources(.) | index("arn:aws:glue:\($region):\($account):table/\($glue_prefix)*/*")))
' "${policy_payload}" >/dev/null || \
    error "provider test IAM policy does not contain the expected scoped S3 and Glue statements"

probe_db="${FLOE_AWS_GLUE_DATABASE_PREFIX}readiness_$(date -u +%Y%m%d%H%M%S)"

log "Checking Glue create/get/delete access with ${probe_db}"
printf '{"Name":"%s"}\n' "${probe_db}" >"${database_payload}"
aws glue create-database \
    --database-input "file://${database_payload}" \
    "${aws_args[@]}" >/dev/null
aws glue get-database \
    --name "${probe_db}" \
    "${aws_args[@]}" >/dev/null
aws glue delete-database \
    --name "${probe_db}" \
    "${aws_args[@]}" >/dev/null

log "Readiness checks passed"
