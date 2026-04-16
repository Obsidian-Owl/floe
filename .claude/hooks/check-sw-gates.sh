#!/usr/bin/env bash
# Specwright gate check — blocks PR creation unless gates have been run
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

# No Specwright state — skip check
if [[ ! -f "$SESSION_FILE" ]] && [[ ! -f "$LEGACY_WORKFLOW" ]]; then
    exit 0
fi

WORK_ID=""
WORKFLOW_FILE=""
WORK_DIR=""
WORK_ARTIFACTS_ROOT=""

if [[ -f "$SESSION_FILE" ]]; then
    WORK_ID="$(python3 - "$SESSION_FILE" <<'PY'
import json
import sys
from pathlib import Path

session = json.loads(Path(sys.argv[1]).read_text())
print(session.get("attachedWorkId") or "")
PY
)"
fi

if [[ -z "$WORK_ID" ]]; then
    if [[ ! -f "$LEGACY_WORKFLOW" ]]; then
        exit 0
    fi
    WORK_ID="$(python3 - "$LEGACY_WORKFLOW" <<'PY'
import json
import sys
from pathlib import Path

workflow = json.loads(Path(sys.argv[1]).read_text())
print((workflow.get("currentWork") or {}).get("id") or "")
PY
)"
    if [[ -z "$WORK_ID" ]]; then
        exit 0
    fi
    EVIDENCE_DIR="${PROJECT_ARTIFACTS_ROOT}/work/${WORK_ID}/evidence"
else
    WORKFLOW_FILE="${GIT_COMMON_DIR}/specwright/work/${WORK_ID}/workflow.json"
    if [[ ! -f "$WORKFLOW_FILE" ]]; then
        exit 0
    fi

    WORK_DIR="$(python3 - "$WORKFLOW_FILE" <<'PY'
import json
import sys
from pathlib import Path

workflow = json.loads(Path(sys.argv[1]).read_text())
print(workflow.get("workDir") or "")
PY
)"

    WORK_ARTIFACTS_ROOT="$(python3 - "$PROJECT_ARTIFACTS_ROOT/config.json" "${GIT_COMMON_DIR}/specwright/work" "$PROJECT_ROOT" <<'PY'
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
)"

    if [[ -z "$WORK_DIR" ]]; then
        EVIDENCE_DIR="${WORK_ARTIFACTS_ROOT}/${WORK_ID}/evidence"
    else
        EVIDENCE_DIR="${WORK_ARTIFACTS_ROOT}/${WORK_DIR}/evidence"
    fi
fi

# Check if evidence directory exists and has files
if [[ ! -d "$EVIDENCE_DIR" ]] || [[ -z "$(ls -A "$EVIDENCE_DIR" 2>/dev/null)" ]]; then
    echo "WARNING: No Specwright gate evidence found for work '$WORK_ID'." >&2
    echo "Run /sw-verify before creating a PR to ensure quality gates pass." >&2
    echo "Evidence expected at: $EVIDENCE_DIR/" >&2
fi

exit 0
