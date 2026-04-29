"""Regression tests for the uv-security audit wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "testing" / "ci" / "uv-security-audit.sh"


def _run_audit_with_fake_uv(
    tmp_path: Path,
    fake_uv: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    uv_path = tmp_path / "uv"
    uv_path.write_text(fake_uv)
    uv_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.requirement("ALPHA-HARDENING")
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


@pytest.mark.requirement("ALPHA-HARDENING")
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


@pytest.mark.requirement("ALPHA-HARDENING")
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


@pytest.mark.requirement("ALPHA-HARDENING")
def test_uv_security_audit_falls_back_to_pip_audit_when_uv_secure_crashes(
    tmp_path: Path,
) -> None:
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
if [[ "$*" == *"uv-secure"* ]]; then
  printf 'Traceback (most recent call last):\\n'
  printf 'RuntimeError: scanner crashed before analysis\\n'
  exit 3
fi
if [[ "$1" == "export" ]]; then
  output_file=""
  while [[ "$#" -gt 0 ]]; do
    if [[ "$1" == "--output-file" ]]; then
      output_file="$2"
      shift 2
      continue
    fi
    shift
  done
  printf 'safe-package==1.2.3\\n-e ./packages/floe-core\\n' > "${output_file:?}"
  exit 0
fi
if [[ "$*" == *"pip-audit"* ]]; then
  printf 'No known vulnerabilities found\\n'
  exit 0
fi
exit 99
""",
    )

    assert result.returncode == 0
    assert "Traceback (most recent call last):" in result.stdout
    assert "uv-secure scanner crashed after 3 attempts" in result.stderr
    assert "running pip-audit fallback" in result.stderr


@pytest.mark.requirement("ALPHA-HARDENING")
def test_uv_security_audit_fails_when_pip_audit_fallback_finds_vulnerability(
    tmp_path: Path,
) -> None:
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
if [[ "$*" == *"uv-secure"* ]]; then
  printf 'RuntimeError: scanner crashed before analysis\\n'
  exit 3
fi
if [[ "$1" == "export" ]]; then
  output_file=""
  while [[ "$#" -gt 0 ]]; do
    if [[ "$1" == "--output-file" ]]; then
      output_file="$2"
      shift 2
      continue
    fi
    shift
  done
  printf 'vulnerable-package==1.2.3\\n' > "${output_file:?}"
  exit 0
fi
if [[ "$*" == *"pip-audit"* ]]; then
  printf 'Found 1 known vulnerability\\n'
  exit 1
fi
exit 99
""",
    )

    assert result.returncode == 1
    assert "Found 1 known vulnerability" in result.stdout
    assert "running pip-audit fallback" in result.stderr


@pytest.mark.requirement("ALPHA-HARDENING")
def test_uv_security_audit_retries_transient_scanner_crash(tmp_path: Path) -> None:
    state_file = tmp_path / "attempts"
    result = _run_audit_with_fake_uv(
        tmp_path,
        """#!/usr/bin/env bash
state="${UV_FAKE_STATE:?}"
attempt=0
if [[ -f "${state}" ]]; then
  attempt="$(cat "${state}")"
fi
attempt=$((attempt + 1))
printf '%s' "${attempt}" > "${state}"
if [[ "${attempt}" -eq 1 ]]; then
  printf 'Error: agate raised exception: transient metadata fetch failure\\n'
  exit 3
fi
printf 'No vulnerabilities or maintenance issues detected!\\n'
exit 0
""",
        extra_env={"UV_FAKE_STATE": str(state_file)},
    )

    assert result.returncode == 0
    assert "uv-secure scanner crashed on attempt 1/3" in result.stderr
    assert state_file.read_text() == "2"
