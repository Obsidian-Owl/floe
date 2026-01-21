#!/usr/bin/env bash
# Pre-commit hook: Validate Claude Code agent definitions
#
# Checks that all agent files in .claude/agents/ have proper YAML frontmatter
# required for Task tool registration.
#
# Required format:
#   ---
#   name: agent-name
#   description: What this agent does
#   tools: Read, Glob, Grep, Bash
#   model: haiku|sonnet|opus
#   ---

set -euo pipefail

AGENTS_DIR=".claude/agents"
ERRORS=0

# Check if agents directory exists
if [[ ! -d "$AGENTS_DIR" ]]; then
    echo "No agents directory found at $AGENTS_DIR"
    exit 0
fi

# Check each agent file
for agent_file in "$AGENTS_DIR"/*.md; do
    [[ -e "$agent_file" ]] || continue

    filename=$(basename "$agent_file")

    # Check for YAML frontmatter start
    if ! head -1 "$agent_file" | grep -q "^---$"; then
        echo "ERROR: $filename - Missing YAML frontmatter (first line must be '---')" >&2
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # Extract frontmatter (between first and second ---)
    # Use awk for cross-platform compatibility (macOS head doesn't support -n -1)
    frontmatter=$(awk 'NR==1{next} /^---$/{exit} {print}' "$agent_file")

    # Check for required fields
    if ! echo "$frontmatter" | grep -q "^name:"; then
        echo "ERROR: $filename - Missing 'name:' field in frontmatter" >&2
        ERRORS=$((ERRORS + 1))
    fi

    if ! echo "$frontmatter" | grep -q "^description:"; then
        echo "ERROR: $filename - Missing 'description:' field in frontmatter" >&2
        ERRORS=$((ERRORS + 1))
    fi

    if ! echo "$frontmatter" | grep -q "^tools:"; then
        echo "ERROR: $filename - Missing 'tools:' field in frontmatter" >&2
        ERRORS=$((ERRORS + 1))
    fi

    if ! echo "$frontmatter" | grep -q "^model:"; then
        echo "ERROR: $filename - Missing 'model:' field in frontmatter" >&2
        ERRORS=$((ERRORS + 1))
    fi

    # Validate model value
    model_value=$(echo "$frontmatter" | grep "^model:" | sed 's/model: *//')
    if [[ -n "$model_value" ]] && ! echo "$model_value" | grep -qE "^(haiku|sonnet|opus)$"; then
        echo "ERROR: $filename - Invalid model '$model_value' (must be haiku, sonnet, or opus)" >&2
        ERRORS=$((ERRORS + 1))
    fi
done

if [[ $ERRORS -gt 0 ]]; then
    echo "" >&2
    echo "Found $ERRORS agent validation error(s)" >&2
    echo "" >&2
    echo "Required frontmatter format:" >&2
    echo "  ---" >&2
    echo "  name: agent-name" >&2
    echo "  description: What this agent does" >&2
    echo "  tools: Read, Glob, Grep, Bash" >&2
    echo "  model: haiku|sonnet|opus" >&2
    echo "  ---" >&2
    exit 1
fi

echo "All $(ls -1 "$AGENTS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ') agents validated successfully"
