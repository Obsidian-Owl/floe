"""Regression tests for the uv-security audit wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "testing" / "ci" / "uv-security-audit.sh"


def _run_audit_with_fake_uv(tmp_path: Path, fake_uv: str) -> subprocess.CompletedProcess[str]:
    uv_path = tmp_path / "uv"
    uv_path.write_text(fake_uv)
    uv_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"

    return subprocess.run(
        [str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_uv_security_audit_fails_when_uv_secure_cannot_spawn(tmp_path: Path) -> None:
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
printf 'error: Failed to spawn: uv-secure\\n' >&2
exit 2
""",
    )

    assert result.returncode == 1
    assert "Failed to spawn: uv-secure" in result.stdout
    assert "uv-secure invocation or configuration failed" in result.stderr


def test_uv_security_audit_fails_for_positive_vulnerability_count(tmp_path: Path) -> None:
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
printf 'Vulnerable: 12 vulnerabilities\\n'
exit 2
""",
    )

    assert result.returncode == 1
    assert "Vulnerabilities detected" in result.stderr


def test_uv_security_audit_allows_warning_exit_without_invocation_or_vulnerability_error(
    tmp_path: Path,
) -> None:
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
printf 'No vulnerabilities or maintenance issues detected!\\n'
exit 2
""",
    )

    assert result.returncode == 0
    assert "uv-secure returned warnings (exit code 2)" in result.stderr
