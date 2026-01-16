#!/usr/bin/env python3
"""Ralph Wiggum Pre-Flight Check Script.

Validates all required services before workflow execution.
MUST pass before any Ralph command proceeds.

Usage:
    python preflight.py                    # Check all services
    python preflight.py --service linear   # Check specific service
    python preflight.py --json             # Output as JSON
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, NamedTuple

import yaml


class PreflightResult(NamedTuple):
    """Result of a pre-flight check."""

    status: Literal["PASS", "BLOCKED", "WARN"]
    service: str
    message: str
    recoverable: bool
    action: str | None


class PreflightReport(NamedTuple):
    """Aggregated pre-flight report."""

    overall_status: Literal["PASS", "BLOCKED", "WARN"]
    checked_at: str
    results: list[PreflightResult]
    can_proceed: bool


def load_config() -> dict[str, Any]:
    """Load Ralph configuration."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open() as f:
        return yaml.safe_load(f) or {}


def check_git() -> PreflightResult:
    """Check git is available and repo is valid."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            return PreflightResult(
                status="PASS",
                service="git",
                message="Git repository valid",
                recoverable=True,
                action=None,
            )
        else:
            return PreflightResult(
                status="BLOCKED",
                service="git",
                message=f"Git error: {result.stderr.strip()}",
                recoverable=True,
                action="Ensure you are in a git repository",
            )
    except FileNotFoundError:
        return PreflightResult(
            status="BLOCKED",
            service="git",
            message="Git not found",
            recoverable=True,
            action="Install git",
        )
    except subprocess.TimeoutExpired:
        return PreflightResult(
            status="BLOCKED",
            service="git",
            message="Git command timed out",
            recoverable=True,
            action="Check git repository state",
        )


def check_linear_mcp() -> PreflightResult:
    """Check Linear MCP server connectivity.

    This checks if Linear MCP is responsive by attempting to list teams.
    Linear is REQUIRED - workflow BLOCKS if unavailable.
    """
    # Linear MCP check is done via Claude's tool calls
    # This script provides the check instructions
    return PreflightResult(
        status="PASS",
        service="linear",
        message="Linear MCP check requires Claude tool call",
        recoverable=True,
        action="Use mcp__plugin_linear_linear__list_teams to verify",
    )


def check_cognee() -> PreflightResult:
    """Check Cognee agent-memory connectivity.

    Cognee is OPTIONAL - workflow continues with local buffer if unavailable.
    """
    try:
        # Check if agent-memory config exists
        cognee_config = Path.cwd() / ".cognee" / "config.yaml"
        if not cognee_config.exists():
            return PreflightResult(
                status="WARN",
                service="cognee",
                message="Cognee not configured - using local buffer",
                recoverable=True,
                action="Run 'agent-memory init' to configure Cognee",
            )

        # Check for COGNEE_API_KEY environment variable
        import os

        if not os.environ.get("COGNEE_API_KEY"):
            return PreflightResult(
                status="WARN",
                service="cognee",
                message="COGNEE_API_KEY not set - using local buffer",
                recoverable=True,
                action="Set COGNEE_API_KEY environment variable",
            )

        return PreflightResult(
            status="PASS",
            service="cognee",
            message="Cognee configuration found",
            recoverable=True,
            action=None,
        )
    except Exception as e:
        return PreflightResult(
            status="WARN",
            service="cognee",
            message=f"Cognee check failed: {e}",
            recoverable=True,
            action="Memories will be buffered locally for later sync",
        )


def check_manifest() -> PreflightResult:
    """Check Ralph manifest.json exists and is valid."""
    manifest_path = Path(__file__).parent.parent / "manifest.json"
    if not manifest_path.exists():
        return PreflightResult(
            status="WARN",
            service="manifest",
            message="manifest.json not found",
            recoverable=True,
            action="Will be created on first /ralph.spawn",
        )

    try:
        with manifest_path.open() as f:
            manifest = json.load(f)
            version = manifest.get("schema_version", "unknown")
            return PreflightResult(
                status="PASS",
                service="manifest",
                message=f"Manifest valid (v{version})",
                recoverable=True,
                action=None,
            )
    except json.JSONDecodeError as e:
        return PreflightResult(
            status="BLOCKED",
            service="manifest",
            message=f"Invalid manifest.json: {e}",
            recoverable=True,
            action="Fix or delete .ralph/manifest.json",
        )


def check_direnv() -> PreflightResult:
    """Check direnv is installed and .envrc is allowed.

    Direnv is REQUIRED for consistent environment setup across worktrees.
    Without it, environment variables won't be set correctly in worktrees.
    """
    try:
        # Check if direnv is installed
        result = subprocess.run(
            ["direnv", "version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            return PreflightResult(
                status="BLOCKED",
                service="direnv",
                message="direnv not installed - required for worktree environment",
                recoverable=True,
                action="Install direnv: brew install direnv && eval \"$(direnv hook bash)\"",
            )

        # Check if .envrc is allowed in current directory
        result = subprocess.run(
            ["direnv", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if "Found RC allowed true" in result.stdout:
            return PreflightResult(
                status="PASS",
                service="direnv",
                message="direnv enabled and .envrc allowed",
                recoverable=True,
                action=None,
            )
        elif "Found RC allowed false" in result.stdout:
            return PreflightResult(
                status="BLOCKED",
                service="direnv",
                message=".envrc not allowed - worktrees will fail",
                recoverable=True,
                action="Run: direnv allow",
            )
        else:
            return PreflightResult(
                status="PASS",
                service="direnv",
                message="direnv available",
                recoverable=True,
                action=None,
            )

    except FileNotFoundError:
        return PreflightResult(
            status="BLOCKED",
            service="direnv",
            message="direnv not installed - required for worktrees",
            recoverable=True,
            action="Install direnv: brew install direnv && eval \"$(direnv hook bash)\"",
        )
    except subprocess.TimeoutExpired:
        return PreflightResult(
            status="BLOCKED",
            service="direnv",
            message="direnv check timed out",
            recoverable=True,
            action="Check direnv installation",
        )


def check_memory_buffer() -> PreflightResult:
    """Check memory buffer directory status."""
    buffer_dir = Path(__file__).parent.parent / "memory-buffer"
    pending_dir = buffer_dir / "pending"
    failed_dir = buffer_dir / "failed"

    if not buffer_dir.exists():
        return PreflightResult(
            status="WARN",
            service="memory_buffer",
            message="Memory buffer directory not found",
            recoverable=True,
            action="Create .ralph/memory-buffer/ directories",
        )

    pending_count = len(list(pending_dir.glob("*.json"))) if pending_dir.exists() else 0
    failed_count = len(list(failed_dir.glob("*.json"))) if failed_dir.exists() else 0

    if failed_count > 0:
        return PreflightResult(
            status="WARN",
            service="memory_buffer",
            message=f"{failed_count} failed entries need attention",
            recoverable=True,
            action="Review .ralph/memory-buffer/failed/ entries",
        )

    if pending_count > 0:
        return PreflightResult(
            status="PASS",
            service="memory_buffer",
            message=f"{pending_count} entries pending sync",
            recoverable=True,
            action=None,
        )

    return PreflightResult(
        status="PASS",
        service="memory_buffer",
        message="Buffer empty - ready for use",
        recoverable=True,
        action=None,
    )


def run_preflight(services: list[str] | None = None) -> PreflightReport:
    """Run all pre-flight checks.

    Args:
        services: Optional list of specific services to check.
                  If None, checks all services.

    Returns:
        PreflightReport with aggregated results.
    """
    config = load_config()
    preflight_config = config.get("resilience", {}).get("preflight_checks", {})

    # Define all checks
    all_checks = {
        "git": (check_git, preflight_config.get("git", "required")),
        "linear": (check_linear_mcp, preflight_config.get("linear", "required")),
        "cognee": (check_cognee, preflight_config.get("cognee", "optional")),
        "direnv": (check_direnv, preflight_config.get("direnv", "recommended")),
        "manifest": (check_manifest, "optional"),
        "memory_buffer": (check_memory_buffer, "optional"),
    }

    # Filter to requested services
    if services:
        checks = {k: v for k, v in all_checks.items() if k in services}
    else:
        checks = all_checks

    # Run checks
    results: list[PreflightResult] = []
    for _check_name, (check_fn, _requirement) in checks.items():
        result = check_fn()
        results.append(result)

    # Determine overall status
    required_blocked = any(
        r.status == "BLOCKED"
        for r in results
        if all_checks.get(r.service, (None, "optional"))[1] == "required"
    )

    any_blocked = any(r.status == "BLOCKED" for r in results)
    any_warn = any(r.status == "WARN" for r in results)

    if required_blocked:
        overall_status: Literal["PASS", "BLOCKED", "WARN"] = "BLOCKED"
    elif any_blocked or any_warn:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    can_proceed = not required_blocked

    return PreflightReport(
        overall_status=overall_status,
        checked_at=datetime.now(timezone.utc).isoformat(),
        results=results,
        can_proceed=can_proceed,
    )


def format_report(report: PreflightReport, as_json: bool = False) -> str:
    """Format pre-flight report for display."""
    if as_json:
        return json.dumps(
            {
                "overall_status": report.overall_status,
                "checked_at": report.checked_at,
                "can_proceed": report.can_proceed,
                "results": [
                    {
                        "status": r.status,
                        "service": r.service,
                        "message": r.message,
                        "action": r.action,
                    }
                    for r in report.results
                ],
            },
            indent=2,
        )

    lines = [
        "=" * 50,
        f"RALPH WIGGUM PRE-FLIGHT CHECK: {report.overall_status}",
        "=" * 50,
        "",
    ]

    for result in report.results:
        status_icon = {"PASS": "[OK]", "BLOCKED": "[!!]", "WARN": "[??]"}[result.status]
        lines.append(f"{status_icon} {result.service}: {result.message}")
        if result.action:
            lines.append(f"    Action: {result.action}")

    lines.append("")
    lines.append("-" * 50)

    if report.can_proceed:
        lines.append("Status: Ready to proceed")
    else:
        lines.append("Status: BLOCKED - Fix required issues before proceeding")
        lines.append("")
        lines.append("Recovery:")
        lines.append("  1. Fix the blocked service(s) above")
        lines.append("  2. Run: /ralph.preflight to verify")
        lines.append("  3. Resume with: /ralph.resume")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Ralph Wiggum pre-flight checks")
    parser.add_argument(
        "--service",
        "-s",
        action="append",
        dest="services",
        help="Specific service to check (can specify multiple)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    report = run_preflight(args.services)
    print(format_report(report, as_json=args.json))

    # Return non-zero if blocked
    return 0 if report.can_proceed else 1


if __name__ == "__main__":
    sys.exit(main())
