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

echo "Installing chained hooks to: $HOOKS_DIR"

# Pre-commit hook (runs on every commit)
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/usr/bin/env sh
# Chained hook: bd (beads) + pre-commit framework
# Installed by: scripts/setup-hooks.sh

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
    echo "Warning: pre-commit not found, skipping code quality checks" >&2
    echo "  Install: uv add pre-commit --dev" >&2
fi
HOOK

# Pre-push hook (runs before push - slower checks)
cat > "$HOOKS_DIR/pre-push" << 'HOOK'
#!/usr/bin/env sh
# Chained hook: bd (beads) + pre-commit framework
# Installed by: scripts/setup-hooks.sh

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
    echo "Warning: pre-commit not found, skipping pre-push checks" >&2
fi
HOOK

# Prepare-commit-msg hook (bd only - for issue references)
cat > "$HOOKS_DIR/prepare-commit-msg" << 'HOOK'
#!/usr/bin/env sh
# bd (beads) hook for commit message preparation
# Installed by: scripts/setup-hooks.sh

if command -v bd >/dev/null 2>&1; then
    exec bd hooks run prepare-commit-msg "$@"
fi
HOOK

# Post-checkout hook (bd only - for branch tracking)
cat > "$HOOKS_DIR/post-checkout" << 'HOOK'
#!/usr/bin/env sh
# bd (beads) hook for checkout tracking
# Installed by: scripts/setup-hooks.sh

if command -v bd >/dev/null 2>&1; then
    exec bd hooks run post-checkout "$@"
fi
HOOK

# Post-merge hook (bd only - for merge tracking)
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env sh
# bd (beads) hook for merge tracking
# Installed by: scripts/setup-hooks.sh

if command -v bd >/dev/null 2>&1; then
    exec bd hooks run post-merge "$@"
fi
HOOK

# Make all hooks executable
chmod +x "$HOOKS_DIR/pre-commit" \
         "$HOOKS_DIR/pre-push" \
         "$HOOKS_DIR/prepare-commit-msg" \
         "$HOOKS_DIR/post-checkout" \
         "$HOOKS_DIR/post-merge"

echo ""
echo "Hooks installed successfully:"
echo "  - pre-commit:         bd + ruff, bandit, trailing-whitespace, etc."
echo "  - pre-push:           bd + mypy --strict, pytest unit tests"
echo "  - prepare-commit-msg: bd (issue references)"
echo "  - post-checkout:      bd (branch tracking)"
echo "  - post-merge:         bd (merge tracking)"
echo ""
echo "Note: Run this script again after 'bd hooks install' or 'pre-commit install'"
echo "      to restore chained hooks."
