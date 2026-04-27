#!/usr/bin/env bash
# Run a Docker command with a predictable config for public registry pulls.
#
# DevPod and some CI environments can inject Docker credential helpers that
# point at ephemeral localhost services. Public image pulls should not depend on
# that state. By default this wrapper uses an isolated DOCKER_CONFIG directory
# with an empty config.json, while still allowing explicit opt-out/override.

set -euo pipefail

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <docker-command> [args...]" >&2
    exit 2
fi

CONFIG_MODE="${FLOE_PUBLIC_DOCKER_CONFIG_MODE:-isolated}"
CONFIG_DIR="${FLOE_PUBLIC_DOCKER_CONFIG_DIR:-}"
BUILD_ENGINE="${FLOE_PUBLIC_DOCKER_BUILD_ENGINE:-classic}"
TEMP_CONFIG_DIR=""
SOURCE_DOCKER_CONFIG="${DOCKER_CONFIG:-${HOME}/.docker}"
ACTIVE_DOCKER_CONTEXT=""
HELM_REGISTRY_CONFIG_WRITTEN=""

cleanup() {
    if [[ -n "${TEMP_CONFIG_DIR}" ]]; then
        rm -rf "${TEMP_CONFIG_DIR}"
    fi
}

trap cleanup EXIT

case "${CONFIG_MODE}" in
    isolated|inherit)
        ;;
    *)
        echo "Unsupported FLOE_PUBLIC_DOCKER_CONFIG_MODE='${CONFIG_MODE}'." >&2
        echo "Use 'isolated' or 'inherit'." >&2
        exit 2
        ;;
esac

case "${BUILD_ENGINE}" in
    classic|buildkit)
        ;;
    *)
        echo "Unsupported FLOE_PUBLIC_DOCKER_BUILD_ENGINE='${BUILD_ENGINE}'." >&2
        echo "Use 'classic' or 'buildkit'." >&2
        exit 2
        ;;
esac

if [[ "${CONFIG_MODE}" == "isolated" && "${1:-}" == "docker" && -z "${DOCKER_HOST:-}" ]]; then
    ACTIVE_DOCKER_CONTEXT="$(docker context show 2>/dev/null || true)"
fi

write_isolated_config() {
    local target_dir="$1"

    if [[ -n "${ACTIVE_DOCKER_CONTEXT}" ]]; then
        if command -v python3 >/dev/null 2>&1; then
            ACTIVE_DOCKER_CONTEXT_JSON="${ACTIVE_DOCKER_CONTEXT}" python3 - <<'PY' > "${target_dir}/config.json"
import json
import os
import sys

json.dump(
    {"auths": {}, "currentContext": os.environ["ACTIVE_DOCKER_CONTEXT_JSON"]},
    sys.stdout,
    separators=(",", ":"),
)
sys.stdout.write("\n")
PY
        elif command -v jq >/dev/null 2>&1; then
            jq -cn --arg ctx "${ACTIVE_DOCKER_CONTEXT}" '{"auths":{},"currentContext":$ctx}' \
                > "${target_dir}/config.json"
        elif [[ "${ACTIVE_DOCKER_CONTEXT}" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
            printf '{"auths":{},"currentContext":"%s"}\n' "${ACTIVE_DOCKER_CONTEXT}" > "${target_dir}/config.json"
        else
            echo "Active Docker context contains characters that require JSON escaping; install python3 or jq." >&2
            exit 2
        fi
        if [[ -d "${SOURCE_DOCKER_CONFIG}/contexts" && ! -e "${target_dir}/contexts" ]]; then
            ln -s "${SOURCE_DOCKER_CONFIG}/contexts" "${target_dir}/contexts"
        fi
    else
        printf '{"auths":{}}\n' > "${target_dir}/config.json"
    fi
}

write_isolated_helm_registry_config() {
    local target_file="$1"
    mkdir -p "$(dirname "${target_file}")"
    printf '{"auths":{}}\n' > "${target_file}"
    HELM_REGISTRY_CONFIG_WRITTEN="${target_file}"
}

if [[ -n "${CONFIG_DIR}" ]]; then
    mkdir -p "${CONFIG_DIR}"
    if [[ ! -f "${CONFIG_DIR}/config.json" ]]; then
        write_isolated_config "${CONFIG_DIR}"
    elif [[ -n "${ACTIVE_DOCKER_CONTEXT}" && -d "${SOURCE_DOCKER_CONFIG}/contexts" && ! -e "${CONFIG_DIR}/contexts" ]]; then
        ln -s "${SOURCE_DOCKER_CONFIG}/contexts" "${CONFIG_DIR}/contexts"
    fi
    export DOCKER_CONFIG="${CONFIG_DIR}"
    if [[ "${CONFIG_MODE}" == "isolated" && -z "${HELM_REGISTRY_CONFIG:-}" ]]; then
        write_isolated_helm_registry_config "${CONFIG_DIR}/helm-registry-config.json"
        export HELM_REGISTRY_CONFIG="${HELM_REGISTRY_CONFIG_WRITTEN}"
    fi
elif [[ "${CONFIG_MODE}" == "isolated" ]]; then
    TEMP_CONFIG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/floe-public-docker.XXXXXX")"
    write_isolated_config "${TEMP_CONFIG_DIR}"
    export DOCKER_CONFIG="${TEMP_CONFIG_DIR}"
    if [[ -z "${HELM_REGISTRY_CONFIG:-}" ]]; then
        write_isolated_helm_registry_config "${TEMP_CONFIG_DIR}/helm-registry-config.json"
        export HELM_REGISTRY_CONFIG="${HELM_REGISTRY_CONFIG_WRITTEN}"
    fi
fi

if [[ "${1:-}" == "docker" && "${2:-}" == "build" ]]; then
    if [[ "${BUILD_ENGINE}" == "classic" ]]; then
        export DOCKER_BUILDKIT=0
    else
        unset DOCKER_BUILDKIT || true
    fi
fi

exec "$@"
