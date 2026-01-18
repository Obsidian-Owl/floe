#!/usr/bin/env bash
# Pre-commit hook: Detect hardcoded time.sleep() in test code
# Matches CI check in .github/workflows/ci.yml
#
# Excludes:
# - polling.py (the implementation that needs time.sleep)
# - test_polling_example.py (documentation showing anti-patterns)
# - Commented lines
# - Lines with # Sleep/# Slow/# timeout comments (intentional test fixtures)

set -euo pipefail

VIOLATIONS=$(grep -rI "time\.sleep(" tests/ testing/ packages/*/tests/ plugins/*/tests/ --include="*.py" 2>/dev/null \
    | grep -v "polling\.py" \
    | grep -v "test_polling_example\.py" \
    | grep -v "# .*time\.sleep" \
    | grep -Ev "^\s*#" \
    | grep -v "\.venv/" \
    | grep -v "#.*Sleep" \
    | grep -v "#.*Slow" \
    | grep -v "#.*timeout" \
    | grep -v "#.*simulate" \
    || true)

if [[ -n "$VIOLATIONS" ]]; then
    echo "ERROR: Found hardcoded time.sleep() in test code:" >&2
    echo "$VIOLATIONS" >&2
    echo "" >&2
    echo "Use polling utilities instead:" >&2
    echo "  from testing.fixtures.polling import wait_for_condition" >&2
    exit 1
fi

echo "No problematic hardcoded sleeps found"
