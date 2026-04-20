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

if [[ -n "${CONFIG_DIR}" ]]; then
    mkdir -p "${CONFIG_DIR}"
    if [[ ! -f "${CONFIG_DIR}/config.json" ]]; then
        printf '{"auths":{}}\n' > "${CONFIG_DIR}/config.json"
    fi
    export DOCKER_CONFIG="${CONFIG_DIR}"
elif [[ "${CONFIG_MODE}" == "isolated" ]]; then
    TEMP_CONFIG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/floe-public-docker.XXXXXX")"
    printf '{"auths":{}}\n' > "${TEMP_CONFIG_DIR}/config.json"
    export DOCKER_CONFIG="${TEMP_CONFIG_DIR}"
fi

if [[ "${1:-}" == "docker" && "${2:-}" == "build" ]]; then
    if [[ "${BUILD_ENGINE}" == "classic" ]]; then
        export DOCKER_BUILDKIT=0
    else
        unset DOCKER_BUILDKIT || true
    fi
fi

exec "$@"
