#!/usr/bin/env bash
# scripts/setup-hooks.sh
# Sets up git hooks to run pre-commit framework
#
# Usage: ./scripts/setup-hooks.sh
#
# This script creates git hooks that run:
# 1. pre-commit framework for code quality (ruff, bandit, mypy, etc.)
# 2. Cognee sync for knowledge graph updates
#
# Run this after cloning, or after running `pre-commit install`
# which would otherwise overwrite the hooks.

set -euo pipefail

# Get the git hooks directory (works with worktrees) and force Git to use it
# for this repository, even when the developer has a global core.hooksPath.
GIT_DIR="$(git rev-parse --git-common-dir 2>/dev/null || git rev-parse --git-dir)"
GIT_DIR="$(cd "$GIT_DIR" && pwd)"
HOOKS_DIR="$GIT_DIR/hooks"
GLOBAL_HOOKS_PATH="$(git config --global --get core.hooksPath || true)"
LOCAL_HOOKS_PATH="$(git config --local --get core.hooksPath || true)"

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

if [[ -n "$GLOBAL_HOOKS_PATH" && "$GLOBAL_HOOKS_PATH" != "$HOOKS_DIR" ]]; then
    echo "Overriding global core.hooksPath for this repository:"
    echo "  global: $GLOBAL_HOOKS_PATH"
    echo "  local:  $HOOKS_DIR"
fi

if [[ "$LOCAL_HOOKS_PATH" != "$HOOKS_DIR" ]]; then
    git config --local core.hooksPath "$HOOKS_DIR"
fi

# Backup existing hooks if they exist and weren't created by this script
BACKUP_DIR="$HOOKS_DIR/backup.$(date +%Y%m%d-%H%M%S)"
HOOKS_TO_INSTALL="pre-commit post-commit pre-push post-merge"
NEEDS_BACKUP=false

for hook in $HOOKS_TO_INSTALL; do
    if [[ -f "$HOOKS_DIR/$hook" ]]; then
        # Check if it's our hook (contains our marker)
        if ! grep -q "Installed by: scripts/setup-hooks.sh" "$HOOKS_DIR/$hook" 2>/dev/null; then
            NEEDS_BACKUP=true
            break
        fi
    fi
done

if [[ "$NEEDS_BACKUP" = true ]]; then
    mkdir -p "$BACKUP_DIR"
    for hook in $HOOKS_TO_INSTALL; do
        if [[ -f "$HOOKS_DIR/$hook" ]]; then
            if ! grep -q "Installed by: scripts/setup-hooks.sh" "$HOOKS_DIR/$hook" 2>/dev/null; then
                cp "$HOOKS_DIR/$hook" "$BACKUP_DIR/$hook"
                echo "Backed up existing $hook to $BACKUP_DIR/"
            fi
        fi
    done
fi

echo "Installing hooks to: $HOOKS_DIR"

# Pre-commit hook (runs on every commit)
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# pre-commit framework hook
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

if command -v uv >/dev/null 2>&1; then
    exec uv run --no-sync pre-commit run --hook-stage pre-commit
elif command -v pre-commit >/dev/null 2>&1; then
    exec pre-commit run --hook-stage pre-commit
else
    echo "ERROR: pre-commit not found - code quality checks cannot run" >&2
    echo "  Install: uv add pre-commit --dev && make setup-hooks" >&2
    exit 1
fi
HOOK

# Post-commit hook (runs after successful commit - triggers Cognee sync)
cat > "$HOOKS_DIR/post-commit" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# Cognee knowledge graph sync hook
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# Get repo root (works with worktrees)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Run Cognee sync in async mode (non-blocking)
# Only sync if the cognee-sync script exists
if [ -x "$REPO_ROOT/scripts/cognee-sync" ]; then
    "$REPO_ROOT/scripts/cognee-sync" --async 2>/dev/null &
fi
HOOK

# Pre-push hook (runs before push - slower checks)
cat > "$HOOKS_DIR/pre-push" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# pre-commit framework hook (pre-push stage)
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# Git hooks run with repository-local GIT_* variables exported. Clear them
# before invoking test subprocesses that create their own temporary repos.
for git_env_var in $(git rev-parse --local-env-vars); do
    case "$git_env_var" in
        GIT_*[!ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_]*)
            continue
            ;;
        GIT_*)
            unset "$git_env_var"
            ;;
    esac
done

if command -v uv >/dev/null 2>&1; then
    exec uv run --no-sync pre-commit run --hook-stage pre-push --all-files
elif command -v pre-commit >/dev/null 2>&1; then
    exec pre-commit run --hook-stage pre-push --all-files
else
    echo "ERROR: pre-commit not found - pre-push checks cannot run" >&2
    echo "  Install: uv add pre-commit --dev && make setup-hooks" >&2
    exit 1
fi
HOOK

# Post-merge hook (Cognee full rebuild)
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# Cognee full rebuild hook
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# Run Cognee full sync in async mode (non-blocking)
# Full rebuild on merge since many files may have changed
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [ -x "$REPO_ROOT/scripts/cognee-sync" ]; then
    "$REPO_ROOT/scripts/cognee-sync" --all --async 2>/dev/null &
fi
HOOK

# Make all hooks executable
chmod +x "$HOOKS_DIR/pre-commit" \
         "$HOOKS_DIR/post-commit" \
         "$HOOKS_DIR/pre-push" \
         "$HOOKS_DIR/post-merge"

# Remove old bd-only hooks that are no longer needed
rm -f "$HOOKS_DIR/prepare-commit-msg" "$HOOKS_DIR/post-checkout"

echo ""
echo "Hooks installed successfully:"
echo "  - pre-commit:   ruff, bandit, secrets, sleep-detection, etc."
echo "  - post-commit:  Cognee async sync (non-blocking)"
echo "  - pre-push:     CI-aligned lint, type, security, test, and traceability checks"
echo "  - post-merge:   Cognee full rebuild (non-blocking)"
echo ""
echo "Quality bar alignment:"
echo "  - Pre-commit: Fast checks (<5s) matching CI lint stage"
echo "  - Pre-push:   Thorough checks matching CI test stages"
echo "  - hooksPath:  repo-local core.hooksPath -> $HOOKS_DIR"
echo ""
echo "Note: Run 'make setup-hooks' again after 'pre-commit install'"
echo "      to restore hooks."
