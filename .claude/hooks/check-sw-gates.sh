#!/usr/bin/env bash
# Specwright gate check — advisory reminder to run gates before creating a PR
#
# Checks for evidence files in the active work unit's evidence/ directory.
# If no evidence exists, warns the agent to run /sw-verify first.
#
# This is ADVISORY — it prints a warning but does not block (exit 0).
# The agent should respect the warning and run verification.

set -euo pipefail

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
PROJECT_ARTIFACTS_ROOT="${PROJECT_ROOT}/.specwright"
GIT_DIR="$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-dir 2>/dev/null || true)"
GIT_COMMON_DIR="$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
SESSION_FILE="${GIT_DIR:+$GIT_DIR/specwright/session.json}"
LEGACY_WORKFLOW="${PROJECT_ARTIFACTS_ROOT}/state/workflow.json"

warn() {
    echo "WARNING: $1" >&2
}

read_json_field() {
    local json_file="$1"
    local field_path="$2"

    python3 - "$json_file" "$field_path" <<'PY'
import json
import sys
from pathlib import Path

json_path = Path(sys.argv[1])
field_path = sys.argv[2]

data = json.loads(json_path.read_text())
value = data
for part in field_path.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = ""
        break

print(value or "")
PY
}

resolve_work_artifacts_root() {
    local config_path="$1"
    local default_root="$2"
    local project_root="$3"

    python3 - "$config_path" "$default_root" "$project_root" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
default_root = Path(sys.argv[2])
project_root = Path(sys.argv[3])

if not config_path.exists():
    print(default_root)
    raise SystemExit(0)

config = json.loads(config_path.read_text())
work_artifacts = ((config.get("git") or {}).get("workArtifacts") or {})
if work_artifacts.get("mode") == "tracked" and work_artifacts.get("trackedRoot"):
    print(project_root / work_artifacts["trackedRoot"])
else:
    print(default_root)
PY
}

# No Specwright state — skip check
if [[ ! -f "$SESSION_FILE" ]] && [[ ! -f "$LEGACY_WORKFLOW" ]]; then
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not available; skipping Specwright gate evidence check."
    exit 0
fi

WORK_ID=""
WORKFLOW_FILE=""
WORK_DIR=""
WORK_ARTIFACTS_ROOT=""

if [[ -f "$SESSION_FILE" ]]; then
    WORK_ID="$(read_json_field "$SESSION_FILE" "attachedWorkId" || true)"
fi

if [[ -z "$WORK_ID" ]]; then
    if [[ ! -f "$LEGACY_WORKFLOW" ]]; then
        exit 0
    fi
    WORK_ID="$(read_json_field "$LEGACY_WORKFLOW" "currentWork.id" || true)"
    if [[ -z "$WORK_ID" ]]; then
        exit 0
    fi
    EVIDENCE_DIR="${PROJECT_ARTIFACTS_ROOT}/work/${WORK_ID}/evidence"
else
    WORKFLOW_FILE="${GIT_COMMON_DIR:+$GIT_COMMON_DIR/specwright/work/${WORK_ID}/workflow.json}"
    if [[ -z "$WORKFLOW_FILE" ]] || [[ ! -f "$WORKFLOW_FILE" ]]; then
        warn "Specwright runtime workflow not found for work '$WORK_ID'; skipping gate evidence check."
        exit 0
    fi

    WORK_DIR="$(read_json_field "$WORKFLOW_FILE" "workDir" || true)"

    WORK_ARTIFACTS_ROOT="$(resolve_work_artifacts_root "$PROJECT_ARTIFACTS_ROOT/config.json" "${GIT_COMMON_DIR}/specwright/work" "$PROJECT_ROOT" || true)"

    if [[ -z "$WORK_DIR" ]]; then
        EVIDENCE_DIR="${WORK_ARTIFACTS_ROOT}/${WORK_ID}/evidence"
    else
        EVIDENCE_DIR="${WORK_ARTIFACTS_ROOT}/${WORK_DIR}/evidence"
    fi
fi

# Check if evidence directory exists and has files
if [[ ! -d "$EVIDENCE_DIR" ]] || ! find "$EVIDENCE_DIR" -mindepth 1 -print -quit | grep -q .; then
    warn "No Specwright gate evidence found for work '$WORK_ID'."
    warn "Run /sw-verify before creating a PR to ensure quality gates pass."
    warn "Evidence expected at: $EVIDENCE_DIR/"
fi

exit 0
