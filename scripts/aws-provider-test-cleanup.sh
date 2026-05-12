#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-cleanup] $*" >&2
}

error() {
    echo "[aws-provider-cleanup] ERROR: $*" >&2
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
require_env FLOE_PROVIDER_SPIKE_RUN

aws_args=(--region "${FLOE_AWS_REGION}")
test_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}"
run_prefix="${test_prefix}${FLOE_PROVIDER_SPIKE_RUN}/"
run_database="${FLOE_AWS_GLUE_DATABASE_PREFIX}${FLOE_PROVIDER_SPIKE_RUN//-/_}"
glue_stderr="$(mktemp)"

cleanup_temp() {
    rm -f "${glue_stderr}"
}
trap cleanup_temp EXIT

validate_inputs() {
    if [[ ! "${FLOE_PROVIDER_SPIKE_RUN}" =~ ^floe-provider-[0-9]{8}T[0-9]{6}Z$ ]]; then
        error "FLOE_PROVIDER_SPIKE_RUN must match ^floe-provider-[0-9]{8}T[0-9]{6}Z$"
    fi

    if [[ ! "${test_prefix}" =~ ^runs/$ ]]; then
        error "FLOE_AWS_TEST_PREFIX must match ^runs/$ for first live validation"
    fi

    if [[ ! "${FLOE_AWS_GLUE_DATABASE_PREFIX}" =~ ^floe_provider_$ ]]; then
        error "FLOE_AWS_GLUE_DATABASE_PREFIX must match ^floe_provider_$ for first live validation"
    fi

    if [[ "${run_prefix}" != "runs/${FLOE_PROVIDER_SPIKE_RUN}/" ]]; then
        error "computed run_prefix is outside the allowed cleanup target: ${run_prefix}"
    fi

    if [[ "${run_database}" != "floe_provider_${FLOE_PROVIDER_SPIKE_RUN//-/_}" ]]; then
        error "computed run_database is outside the allowed cleanup target: ${run_database}"
    fi
}

glue_database_state() {
    : >"${glue_stderr}"
    if aws glue get-database \
        --name "${run_database}" \
        "${aws_args[@]}" >/dev/null 2>"${glue_stderr}"; then
        echo "exists"
        return 0
    fi

    if grep -q "EntityNotFoundException" "${glue_stderr}"; then
        echo "absent"
        return 0
    fi

    cat "${glue_stderr}" >&2
    echo "error"
    return 0
}

validate_inputs

log "Cleaning S3 run prefix s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}"
aws s3 rm "s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}" --recursive "${aws_args[@]}"

log "Deleting Glue tables in ${run_database} if the database exists"
database_state="$(glue_database_state)"
if [[ "${database_state}" == "error" ]]; then
    error "failed to check Glue database: ${run_database}"
fi

if [[ "${database_state}" == "exists" ]]; then
    table_names="$(
        aws glue get-tables \
            --database-name "${run_database}" \
            --query 'TableList[].Name' \
            --output text \
            "${aws_args[@]}"
    )"
    for table_name in ${table_names}; do
        aws glue delete-table \
            --database-name "${run_database}" \
            --name "${table_name}" \
            "${aws_args[@]}" >/dev/null
    done
    aws glue delete-database \
        --database-name "${run_database}" \
        "${aws_args[@]}" >/dev/null
fi

log "Post-cleanup S3 inventory"
s3_remaining_count="$(
    aws s3api list-objects-v2 \
        --bucket "${FLOE_AWS_TEST_BUCKET}" \
        --prefix "${run_prefix}" \
        --query "length(Contents || \`[]\`)" \
        --output text \
        "${aws_args[@]}"
)"

if [[ "${s3_remaining_count}" != "0" ]]; then
    aws s3api list-objects-v2 \
        --bucket "${FLOE_AWS_TEST_BUCKET}" \
        --prefix "${run_prefix}" \
        --max-items 10 \
        "${aws_args[@]}" >&2
    error "S3 objects still exist under s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}"
fi

aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${run_prefix}" \
    --max-items 10 \
    "${aws_args[@]}"

log "Post-cleanup Glue inventory"
database_state="$(glue_database_state)"
if [[ "${database_state}" == "exists" ]]; then
    error "Glue database still exists: ${run_database}"
fi
if [[ "${database_state}" == "error" ]]; then
    error "failed to verify Glue database cleanup: ${run_database}"
fi

log "Cleanup checks passed"
