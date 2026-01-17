#!/usr/bin/env bash
# Constitution validation for pre-commit (lightweight)
# Secret detection delegated to detect-secrets
# Architecture enforcement delegated to import-linter
set -euo pipefail

YELLOW='\033[1;33m'
NC='\033[0m'

WARNINGS=0

# =============================================================================
# Check 1: Branch naming convention (warning only)
# =============================================================================
check_branch_naming() {
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

    if [[ "$branch" == "HEAD" ]] || [[ "$branch" == "unknown" ]] || \
       [[ "$branch" == "main" ]] || [[ "$branch" == "master" ]]; then
        return 0
    fi

    # Valid patterns: epic/*, feat/*, fix/*, chore/*, docs/*, or {number}{letter}-*
    if [[ ! "$branch" =~ ^(epic|feat|fix|chore|docs)/ ]] && [[ ! "$branch" =~ ^[0-9]+[a-z]?- ]]; then
        echo -e "${YELLOW}WARNING: Branch '$branch' doesn't follow convention${NC}" >&2
        echo "  Expected: epic/*, feat/*, fix/*, chore/*, docs/*, or {epic-id}-*" >&2
        echo "  Examples: feat/add-logging, 2a-manifest-validation, epic/plugin-system" >&2
        ((WARNINGS++))
    fi
}

# =============================================================================
# Check 2: Quick architecture reminders (import-linter handles full check)
# =============================================================================
check_quick_architecture() {
    local staged_py_files
    staged_py_files=$(git diff --cached --name-only --diff-filter=ACM | \
                      grep -E '\.py$' | grep -v '/tests/' || true)

    if [[ -z "$staged_py_files" ]]; then
        return 0
    fi

    # Quick check for SQL parsing outside floe-dbt (full check via import-linter on push)
    for file in $staged_py_files; do
        # Skip floe-dbt package
        if [[ "$file" == *"floe-dbt"* ]] || [[ "$file" == *"floe_dbt"* ]]; then
            continue
        fi

        if git show ":$file" 2>/dev/null | grep -E '^[^#]*import (sqlparse|sqlglot)' >/dev/null 2>&1; then
            echo -e "${YELLOW}WARNING: SQL parsing in $file${NC}" >&2
            echo "  Constitution: 'dbt owns SQL' - use dbt for SQL operations" >&2
            ((WARNINGS++))
        fi
    done
}

# =============================================================================
# Main
# =============================================================================
main() {
    check_branch_naming
    check_quick_architecture

    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Constitution: $WARNINGS warning(s) - review before pushing${NC}"
    fi

    # Warnings don't block commits (errors would exit 1)
    return 0
}

main "$@"
exit 0
