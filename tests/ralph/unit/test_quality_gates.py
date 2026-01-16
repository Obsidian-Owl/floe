"""Unit tests for Ralph Wiggum quality gates.

Tests validate the deterministic behavior of quality gates - the anchor
points in the non-deterministic agentic workflow.

Key testing principles:
- Gates are DETERMINISTIC: same input = same output
- Gates are IDEMPOTENT: running twice = same result
- Gates have MONOTONIC progress: passes only increase
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestLintGate:
    """Tests for the lint quality gate (ruff)."""

    @pytest.mark.requirement("ralph-gate-001")
    @pytest.mark.ralph
    def test_lint_gate_deterministic(self, tmp_path: Path) -> None:
        """Lint gate returns same result on repeated runs.

        Validates that the lint gate is deterministic - running it
        multiple times on the same code produces identical results.
        """
        # Create a simple Python file
        test_file = tmp_path / "test_code.py"
        test_file.write_text('def func():\n    return "hello"\n')

        # Run ruff check twice
        result1 = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file), "--output-format=json"],
            capture_output=True,
            text=True,
            check=False,
        )
        result2 = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file), "--output-format=json"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result1.returncode == result2.returncode
        assert result1.stdout == result2.stdout

    @pytest.mark.requirement("ralph-gate-002")
    @pytest.mark.ralph
    def test_lint_gate_detects_issues(self, tmp_path: Path) -> None:
        """Lint gate correctly identifies code issues.

        Validates that ruff detects common issues like unused imports.
        """
        # Create file with unused import
        test_file = tmp_path / "bad_code.py"
        test_file.write_text("import os\n\ndef func():\n    return 1\n")

        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        # Ruff should detect unused import (F401)
        assert result.returncode != 0
        assert "F401" in result.stdout or "os" in result.stdout

    @pytest.mark.requirement("ralph-gate-003")
    @pytest.mark.ralph
    def test_lint_gate_passes_clean_code(self, tmp_path: Path) -> None:
        """Lint gate passes for clean code.

        Validates that well-formatted code passes the lint gate.
        """
        test_file = tmp_path / "clean_code.py"
        clean_code = (
            '"""Module docstring."""\n\n\n'
            'def func() -> str:\n    """Return hello."""\n    return "hello"\n'
        )
        test_file.write_text(clean_code)

        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0


class TestTypeGate:
    """Tests for the type checking quality gate (mypy)."""

    @pytest.mark.requirement("ralph-gate-004")
    @pytest.mark.ralph
    def test_type_gate_deterministic(self, tmp_path: Path) -> None:
        """Type gate returns same result on repeated runs.

        Validates mypy determinism for consistent quality checks.
        """
        test_file = tmp_path / "typed_code.py"
        test_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

        result1 = subprocess.run(
            ["uv", "run", "mypy", str(test_file), "--no-error-summary"],
            capture_output=True,
            text=True,
            check=False,
        )
        result2 = subprocess.run(
            ["uv", "run", "mypy", str(test_file), "--no-error-summary"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result1.returncode == result2.returncode
        assert result1.stdout == result2.stdout

    @pytest.mark.requirement("ralph-gate-005")
    @pytest.mark.ralph
    def test_type_gate_detects_type_errors(self, tmp_path: Path) -> None:
        """Type gate detects type mismatches.

        Validates mypy catches type errors in code.
        """
        test_file = tmp_path / "bad_types.py"
        test_file.write_text("def add(a: int, b: int) -> int:\n    return str(a + b)\n")

        result = subprocess.run(
            ["uv", "run", "mypy", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert "error" in result.stdout.lower()

    @pytest.mark.requirement("ralph-gate-006")
    @pytest.mark.ralph
    def test_type_gate_passes_correct_types(self, tmp_path: Path) -> None:
        """Type gate passes correctly typed code.

        Validates well-typed code passes mypy checks.
        """
        test_file = tmp_path / "good_types.py"
        test_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

        result = subprocess.run(
            ["uv", "run", "mypy", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0


class TestGateIdempotence:
    """Tests for gate idempotence - running twice has same effect."""

    @pytest.mark.requirement("ralph-gate-007")
    @pytest.mark.ralph
    def test_lint_fix_idempotent(self, tmp_path: Path) -> None:
        """Lint fix is idempotent - running twice produces same output.

        After first fix, second run should make no changes.
        """
        test_file = tmp_path / "fixable.py"
        test_file.write_text("x=1+2\n")  # Missing spaces around =

        # First fix
        subprocess.run(
            ["uv", "run", "ruff", "format", str(test_file)],
            capture_output=True,
            check=False,
        )
        content_after_first = test_file.read_text()

        # Second fix
        subprocess.run(
            ["uv", "run", "ruff", "format", str(test_file)],
            capture_output=True,
            check=False,
        )
        content_after_second = test_file.read_text()

        assert content_after_first == content_after_second

    @pytest.mark.requirement("ralph-gate-008")
    @pytest.mark.ralph
    def test_gates_independent(self, tmp_path: Path) -> None:
        """Gates are independent - order doesn't matter.

        Validates that running lint then type check produces
        same result as type check then lint.
        """
        test_file = tmp_path / "code.py"
        code = "def func() -> int:\n    return 42\n"
        test_file.write_text(code)

        # Run lint first, then type
        lint_result = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        type_result1 = subprocess.run(
            ["uv", "run", "mypy", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        # Run type first, then lint
        test_file.write_text(code)  # Reset file
        type_result2 = subprocess.run(
            ["uv", "run", "mypy", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        lint_result2 = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        # Results should be the same regardless of order
        assert lint_result.returncode == lint_result2.returncode
        assert type_result1.returncode == type_result2.returncode


class TestGateMonotonicity:
    """Tests for monotonic progress - passes only increase."""

    @pytest.mark.requirement("ralph-gate-009")
    @pytest.mark.ralph
    def test_fixed_code_passes_gate(self, tmp_path: Path) -> None:
        """Once code is fixed, it stays passing.

        Validates that fixing code makes the gate pass and
        the fix is stable.
        """
        test_file = tmp_path / "evolving.py"

        # Start with bad code
        test_file.write_text("import os\nprint('hello')\n")

        result_before = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            check=False,
        )
        assert result_before.returncode != 0  # Fails due to unused import

        # Fix the code
        test_file.write_text("print('hello')\n")

        result_after = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            check=False,
        )
        assert result_after.returncode == 0  # Now passes

        # Re-run - should still pass
        result_recheck = subprocess.run(
            ["uv", "run", "ruff", "check", str(test_file)],
            capture_output=True,
            check=False,
        )
        assert result_recheck.returncode == 0  # Still passes
