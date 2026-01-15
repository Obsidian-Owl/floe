#!/usr/bin/env bash
# scripts/setup-hooks.sh
# Sets up git hooks to run BOTH bd (beads) AND pre-commit framework
#
# Usage: ./scripts/setup-hooks.sh
#
# This script creates chained git hooks that run:
# 1. bd (beads) hooks for issue tracking JSONL sync
# 2. pre-commit framework for code quality (ruff, bandit, mypy, etc.)
#
# Run this after cloning, or after running `bd hooks install` or `pre-commit install`
# which would otherwise overwrite the chained hooks.

set -euo pipefail

# Get the git hooks directory (works with worktrees)
GIT_DIR="$(git rev-parse --git-common-dir 2>/dev/null || git rev-parse --git-dir)"
HOOKS_DIR="$GIT_DIR/hooks"

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Backup existing hooks if they exist and weren't created by this script
BACKUP_DIR="$HOOKS_DIR/backup.$(date +%Y%m%d-%H%M%S)"
HOOKS_TO_INSTALL="pre-commit post-commit pre-push prepare-commit-msg post-checkout post-merge"
NEEDS_BACKUP=false

for hook in $HOOKS_TO_INSTALL; do
    if [ -f "$HOOKS_DIR/$hook" ]; then
        # Check if it's our hook (contains our marker)
        if ! grep -q "Installed by: scripts/setup-hooks.sh" "$HOOKS_DIR/$hook" 2>/dev/null; then
            NEEDS_BACKUP=true
            break
        fi
    fi
done

if [ "$NEEDS_BACKUP" = true ]; then
    mkdir -p "$BACKUP_DIR"
    for hook in $HOOKS_TO_INSTALL; do
        if [ -f "$HOOKS_DIR/$hook" ]; then
            if ! grep -q "Installed by: scripts/setup-hooks.sh" "$HOOKS_DIR/$hook" 2>/dev/null; then
                cp "$HOOKS_DIR/$hook" "$BACKUP_DIR/$hook"
                echo "Backed up existing $hook to $BACKUP_DIR/"
            fi
        fi
    done
fi

echo "Installing chained hooks to: $HOOKS_DIR"

# Pre-commit hook (runs on every commit)
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# Chained hook: bd (beads) + pre-commit framework
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# 1. Run bd hooks (beads JSONL sync)
if command -v bd >/dev/null 2>&1; then
    bd hooks run pre-commit "$@" || exit $?
fi

# 2. Run pre-commit framework (ruff, bandit, etc.)
if command -v uv >/dev/null 2>&1; then
    exec uv run pre-commit run --hook-stage pre-commit
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
# Chained hook: bd (beads) + pre-commit framework
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# 1. Run bd hooks (beads sync)
if command -v bd >/dev/null 2>&1; then
    bd hooks run pre-push "$@" || exit $?
fi

# 2. Run pre-commit framework (mypy, pytest)
if command -v uv >/dev/null 2>&1; then
    exec uv run pre-commit run --hook-stage pre-push --all-files
elif command -v pre-commit >/dev/null 2>&1; then
    exec pre-commit run --hook-stage pre-push --all-files
else
    echo "ERROR: pre-commit not found - pre-push checks cannot run" >&2
    echo "  Install: uv add pre-commit --dev && make setup-hooks" >&2
    exit 1
fi
HOOK

# Prepare-commit-msg hook (bd only - for issue references)
cat > "$HOOKS_DIR/prepare-commit-msg" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# bd (beads) hook for commit message preparation
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

if command -v bd >/dev/null 2>&1; then
    exec bd hooks run prepare-commit-msg "$@"
fi
HOOK

# Post-checkout hook (bd only - for branch tracking)
cat > "$HOOKS_DIR/post-checkout" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# bd (beads) hook for checkout tracking
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

if command -v bd >/dev/null 2>&1; then
    exec bd hooks run post-checkout "$@"
fi
HOOK

# Post-merge hook (bd + Cognee full rebuild)
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env sh
# AUTO-GENERATED - Do not edit manually
# Chained hook: bd (beads) + Cognee full rebuild
# Installed by: scripts/setup-hooks.sh
# Re-run 'make setup-hooks' to regenerate

# 1. Run bd hooks (beads merge tracking)
if command -v bd >/dev/null 2>&1; then
    bd hooks run post-merge "$@"
fi

# 2. Run Cognee full sync in async mode (non-blocking)
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
         "$HOOKS_DIR/prepare-commit-msg" \
         "$HOOKS_DIR/post-checkout" \
         "$HOOKS_DIR/post-merge"

echo ""
echo "Hooks installed successfully:"
echo "  - pre-commit:         bd + ruff, bandit, trailing-whitespace, etc."
echo "  - post-commit:        Cognee async sync (non-blocking)"
echo "  - pre-push:           bd + mypy --strict, pytest unit tests"
echo "  - prepare-commit-msg: bd (issue references)"
echo "  - post-checkout:      bd (branch tracking)"
echo "  - post-merge:         bd + Cognee full rebuild (non-blocking)"
echo ""
echo "Note: Run 'make setup-hooks' again after 'bd hooks install' or 'pre-commit install'"
echo "      to restore chained hooks."
