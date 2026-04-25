#!/usr/bin/env bash
# Shared DevPod source selection.
#
# Default behavior is remote Git clone from the current branch. Local source
# uploads are intentionally opt-in because this repository can exceed local
# memory/disk budgets during remote E2E validation.

devpod_source_error() {
    echo "[devpod-source] ERROR: $*" >&2
    return 1
}

devpod_bool_true() {
    case "${1:-}" in
        1|true|TRUE|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

devpod_git_branch() {
    local project_root="${1:?project root required}"
    if [[ -n "${DEVPOD_GIT_REF:-}" ]]; then
        printf '%s\n' "${DEVPOD_GIT_REF}"
        return 0
    fi

    git -C "${project_root}" symbolic-ref --quiet --short HEAD
}

devpod_git_remote() {
    local project_root="${1:?project root required}"
    if [[ -n "${DEVPOD_GIT_REMOTE:-}" ]]; then
        printf '%s\n' "${DEVPOD_GIT_REMOTE}"
        return 0
    fi

    git -C "${project_root}" config --get remote.origin.url
}

devpod_git_source_url() {
    local remote="${1:?remote required}"
    local ref="${2:?ref required}"

    # DevPod accepts git:<url>@<ref>. Strip a trailing .git for compatibility
    # with the documented GitHub-style source syntax.
    remote="${remote%.git}"
    printf 'git:%s@%s\n' "${remote}" "${ref}"
}

devpod_assert_remote_ref_exists() {
    local remote="${1:?remote required}"
    local ref="${2:?ref required}"

    git ls-remote --exit-code --heads "${remote}" "${ref}" >/dev/null 2>&1
}

devpod_resolve_source() {
    local project_root="${1:?project root required}"
    local remote
    local ref

    if [[ -n "${DEVPOD_SOURCE:-}" ]]; then
        printf '%s\n' "${DEVPOD_SOURCE}"
        return 0
    fi

    if devpod_bool_true "${DEVPOD_ALLOW_LOCAL_SOURCE:-0}"; then
        printf '%s\n' "${project_root}"
        return 0
    fi

    if ! remote="$(devpod_git_remote "${project_root}")" || [[ -z "${remote}" ]]; then
        devpod_source_error "Cannot resolve remote source. Set DEVPOD_SOURCE or DEVPOD_ALLOW_LOCAL_SOURCE=1."
        return 1
    fi

    if ! ref="$(devpod_git_branch "${project_root}")" || [[ -z "${ref}" || "${ref}" == "HEAD" ]]; then
        devpod_source_error "Cannot resolve a branch ref. Set DEVPOD_GIT_REF or DEVPOD_SOURCE."
        return 1
    fi

    if ! devpod_assert_remote_ref_exists "${remote}" "${ref}"; then
        devpod_source_error "Remote branch '${ref}' is not available on '${remote}'. Push it or set DEVPOD_SOURCE."
        return 1
    fi

    devpod_git_source_url "${remote}" "${ref}"
}
