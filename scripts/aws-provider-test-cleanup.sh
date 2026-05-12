#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-cleanup] $*" >&2
}

require_env() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        echo "[aws-provider-cleanup] ERROR: ${name} is required" >&2
        exit 1
    fi
}

require_env FLOE_AWS_REGION
require_env FLOE_AWS_TEST_BUCKET
require_env FLOE_AWS_GLUE_DATABASE_PREFIX
require_env FLOE_PROVIDER_SPIKE_RUN

aws_args=(--region "${FLOE_AWS_REGION}")
run_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}${FLOE_PROVIDER_SPIKE_RUN}/"
run_database="${FLOE_AWS_GLUE_DATABASE_PREFIX}${FLOE_PROVIDER_SPIKE_RUN//-/_}"

log "Cleaning S3 run prefix s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}"
aws s3 rm "s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}" --recursive "${aws_args[@]}" || true

log "Deleting Glue tables in ${run_database} if the database exists"
if aws glue get-database --name "${run_database}" "${aws_args[@]}" >/dev/null 2>&1; then
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
            "${aws_args[@]}" >/dev/null || true
    done
    aws glue delete-database \
        --database-name "${run_database}" \
        "${aws_args[@]}" >/dev/null || true
fi

log "Post-cleanup S3 inventory"
aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${run_prefix}" \
    --max-items 10 \
    "${aws_args[@]}"

log "Post-cleanup Glue inventory"
aws glue get-database \
    --name "${run_database}" \
    "${aws_args[@]}" >/dev/null 2>&1 && {
        echo "[aws-provider-cleanup] ERROR: Glue database still exists: ${run_database}" >&2
        exit 1
    }

log "Cleanup checks passed"
