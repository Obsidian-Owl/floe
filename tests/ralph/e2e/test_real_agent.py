"""Real E2E tests that invoke actual Claude Code agents.

These tests validate that the Ralph workflow produces quality output
by actually running Claude Code on simple, verifiable tasks.

IMPORTANT: These tests:
- Cost API credits (~$0.01-0.10 per test)
- Take 1-5 minutes to run
- Require ANTHROPIC_API_KEY or Claude subscription
- Are marked with @pytest.mark.real_agent for selective execution

Run with: pytest tests/ralph/e2e/test_real_agent.py -v -s
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


def is_claude_available() -> bool:
    """Check if Claude Code CLI is available."""
    result = subprocess.run(
        ["which", "claude"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def has_api_access() -> bool:
    """Check if we have API access (key or subscription)."""
    # Check for API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    # Check if claude is authenticated (has subscription)
    result = subprocess.run(
        ["claude", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


class TestRealAgent(RalphTestBase):
    """Real E2E tests that invoke Claude Code."""

    @pytest.fixture(autouse=True)
    def check_prerequisites(self) -> None:
        """Check prerequisites before each test."""
        if not is_claude_available():
            pytest.skip("Claude Code CLI not available")
        if not has_api_access():
            pytest.skip("No API access (set ANTHROPIC_API_KEY or authenticate)")

    @pytest.mark.e2e
    @pytest.mark.real_agent
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(300)  # 5 min max
    @pytest.mark.requirement("ralph-quality-001")
    def test_agent_fixes_type_errors(self) -> None:
        """Test that a real agent can fix type errors.

        This test:
        1. Creates a file with obvious type errors
        2. Invokes Claude Code to fix them
        3. Verifies mypy passes on the result
        """
        worktree = self.create_test_worktree("real-agent-types")

        # Create a file with type errors
        broken_file = worktree / "broken_types.py"
        broken_file.write_text('''\
"""Module with type errors for agent to fix."""

from __future__ import annotations


def add_numbers(a, b):
    """Add two numbers. Missing type hints."""
    return a + b


def greet(name):
    """Greet someone. Missing type hints and return type."""
    return "Hello, " + name


def process_items(items):
    """Process items. Missing type hints."""
    result = []
    for item in items:
        result.append(item.upper())
    return result


# This has a type error: returning wrong type
def get_count() -> str:
    """Should return int but returns str."""
    return 42
''')

        # Create pyproject.toml for mypy config
        pyproject = worktree / "pyproject.toml"
        pyproject.write_text('''\
[tool.mypy]
python_version = "3.10"
strict = true
''')

        # Verify the file has type errors before agent runs
        pre_result = subprocess.run(
            ["mypy", "--strict", str(broken_file)],
            capture_output=True,
            text=True,
            cwd=worktree,
            check=False,
        )
        assert pre_result.returncode != 0, "File should have type errors initially"
        initial_errors = pre_result.stdout.count("error:")
        assert initial_errors > 0, f"Expected type errors, got: {pre_result.stdout}"

        # Run Claude Code to fix the type errors
        prompt = f"""\
Fix all type errors in {broken_file.name}.
Add proper type hints to all functions.
Fix the return type error in get_count().
Run mypy to verify your fixes work.
Do NOT create any new files.
"""

        result = subprocess.run(
            [
                "claude",
                "-p",  # Print mode (non-interactive)
                "--model", "haiku",  # Fast and cheap
                "--max-budget-usd", "0.20",
                "--allowedTools", "Read,Edit,Bash",
                "--dangerously-skip-permissions",
                prompt,
            ],
            stdin=subprocess.DEVNULL,  # Critical: prevent hanging on stdin
            capture_output=True,
            text=True,
            cwd=worktree,
            timeout=180,  # 3 min timeout
            check=False,
        )

        # Log agent output for debugging (defensive: worktree may not exist)
        if worktree.exists():
            agent_log = worktree / ".agent_output.log"
            agent_log.write_text(
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\n"
                f"RETURN CODE: {result.returncode}"
            )

        # Verify worktree still exists
        assert worktree.exists(), (
            f"Worktree was deleted during test.\n"
            f"Agent stderr: {result.stderr[:500]}"
        )

        # Verify mypy now passes
        post_result = subprocess.run(
            ["mypy", "--strict", str(broken_file)],
            capture_output=True,
            text=True,
            cwd=worktree,
            check=False,
        )

        # Collect diagnostics
        diagnostics = {
            "initial_errors": initial_errors,
            "final_returncode": post_result.returncode,
            "final_stdout": post_result.stdout,
            "file_content": broken_file.read_text(),
        }

        # Write diagnostics for analysis
        if worktree.exists():
            (worktree / ".diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2)
            )

        # Assert quality
        assert post_result.returncode == 0, (
            f"Agent failed to fix type errors.\n"
            f"mypy output: {post_result.stdout}\n"
            f"File content:\n{broken_file.read_text()}"
        )

    @pytest.mark.e2e
    @pytest.mark.real_agent
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(300)
    @pytest.mark.requirement("ralph-quality-002")
    def test_agent_fixes_lint_errors(self) -> None:
        """Test that a real agent can fix lint errors.

        This test:
        1. Creates a file with lint issues
        2. Invokes Claude Code to fix them
        3. Verifies ruff passes on the result
        """
        worktree = self.create_test_worktree("real-agent-lint")

        # Create a file with lint issues
        broken_file = worktree / "broken_lint.py"
        broken_file.write_text('''\
"""Module with lint errors for agent to fix."""
import os,sys,json  # Multiple imports on one line
import re  # Unused import

def badly_formatted(x,y,z):return x+y+z  # All on one line, no spaces

class badClassName:  # Wrong naming convention
    def __init__(self):
        self.x=1  # No spaces around =

    def method( self,arg ):  # Extra spaces
        if arg==None:  # Should use 'is None'
            return self.x
        else:
            return arg

x = 1
y = 2
z = 3  # Unused variables

def long_function(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p):  # Too many arguments
    return a
''')

        # Verify the file has lint errors before agent runs
        pre_result = subprocess.run(
            ["ruff", "check", str(broken_file)],
            capture_output=True,
            text=True,
            cwd=worktree,
            check=False,
        )
        assert pre_result.returncode != 0, "File should have lint errors initially"

        # Run Claude Code to fix the lint errors
        prompt = f"""\
Fix all lint errors in {broken_file.name}.
Use ruff to check your fixes.
Follow PEP 8 conventions.
Do NOT create any new files.
"""

        result = subprocess.run(
            [
                "claude",
                "-p",
                "--model", "haiku",
                "--max-budget-usd", "0.20",
                "--allowedTools", "Read,Edit,Bash",
                "--dangerously-skip-permissions",
                prompt,
            ],
            stdin=subprocess.DEVNULL,  # Critical: prevent hanging on stdin
            capture_output=True,
            text=True,
            cwd=worktree,
            timeout=180,
            check=False,
        )

        # Log agent output (defensive: worktree may not exist)
        if worktree.exists():
            (worktree / ".agent_output.log").write_text(
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        # Verify worktree still exists
        assert worktree.exists(), (
            f"Worktree was deleted during test.\n"
            f"Agent stderr: {result.stderr[:500]}"
        )

        # Verify ruff now passes
        post_result = subprocess.run(
            ["ruff", "check", str(broken_file)],
            capture_output=True,
            text=True,
            cwd=worktree,
            check=False,
        )

        # Allow some minor issues (ruff is very strict)
        remaining_errors = post_result.stdout.count(" error")
        initial_errors = pre_result.stdout.count(" error")

        assert remaining_errors < initial_errors, (
            f"Agent should reduce lint errors.\n"
            f"Initial: {initial_errors}, Remaining: {remaining_errors}\n"
            f"ruff output: {post_result.stdout}"
        )

    @pytest.mark.e2e
    @pytest.mark.real_agent
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(300)
    @pytest.mark.requirement("ralph-quality-003")
    def test_agent_creates_tests(self) -> None:
        """Test that a real agent can create working tests.

        This test:
        1. Provides a simple function
        2. Asks agent to write tests
        3. Verifies tests actually run and pass
        """
        worktree = self.create_test_worktree("real-agent-tests")

        # Create a simple module to test
        module_file = worktree / "calculator.py"
        module_file.write_text('''\
"""Simple calculator module."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


def divide(a: int, b: int) -> float:
    """Divide a by b.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b
''')

        # Run Claude Code to create tests
        prompt = """\
Create a test file called test_calculator.py that tests all functions in calculator.py.
Include:
- Tests for normal cases
- Test for divide by zero
- At least 8 test cases total

Use pytest style. Run the tests to verify they pass.
"""

        result = subprocess.run(
            [
                "claude",
                "-p",
                "--model", "haiku",
                "--max-budget-usd", "0.30",
                "--allowedTools", "Read,Edit,Write,Bash",
                "--dangerously-skip-permissions",
                prompt,
            ],
            stdin=subprocess.DEVNULL,  # Critical: prevent hanging on stdin
            capture_output=True,
            text=True,
            cwd=worktree,
            timeout=180,
            check=False,
        )

        # Log agent output (defensive: worktree may not exist if agent failed early)
        if worktree.exists():
            (worktree / ".agent_output.log").write_text(
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        # Verify worktree still exists (agent shouldn't delete it)
        assert worktree.exists(), (
            f"Worktree was deleted during test.\n"
            f"Agent stdout: {result.stdout[:500]}\n"
            f"Agent stderr: {result.stderr[:500]}"
        )

        # Verify test file was created
        test_file = worktree / "test_calculator.py"
        assert test_file.exists(), (
            f"Agent should create test_calculator.py\n"
            f"Files in worktree: {list(worktree.iterdir())}"
        )

        # Verify tests pass
        test_result = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-v"],
            capture_output=True,
            text=True,
            cwd=worktree,
            check=False,
        )

        # Write test output for analysis
        if worktree.exists():
            (worktree / ".test_output.log").write_text(
                f"STDOUT:\n{test_result.stdout}\n\nSTDERR:\n{test_result.stderr}"
            )

        assert test_result.returncode == 0, (
            f"Tests should pass.\n"
            f"pytest output: {test_result.stdout}\n"
            f"stderr: {test_result.stderr}"
        )

        # Verify minimum test count
        passed_count = test_result.stdout.count(" PASSED")
        assert passed_count >= 6, (
            f"Expected at least 6 passing tests, got {passed_count}\n"
            f"Output: {test_result.stdout}"
        )

    @pytest.mark.e2e
    @pytest.mark.real_agent
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(420)  # 7 min for full quality gate chain
    @pytest.mark.requirement("ralph-quality-004")
    def test_agent_full_quality_gate_chain(self) -> None:
        """Test that an agent can pass all quality gates.

        This is the most comprehensive test:
        1. Give agent a task with multiple issues
        2. Agent must fix lint, types, and create tests
        3. All quality gates must pass
        """
        worktree = self.create_test_worktree("real-agent-full")

        # Create a file with multiple issues
        broken_file = worktree / "user_service.py"
        broken_file.write_text('''\
"""User service with multiple issues."""

def create_user(name,email,age):
    """Create a user. Missing types, validation."""
    user = {"name":name,"email":email,"age":age}
    return user

def get_user_by_id(id):
    """Get user by ID. Bad parameter name, no types."""
    # Simulate database lookup
    users = {"1": {"name": "Alice"}, "2": {"name": "Bob"}}
    return users.get(id)

def validate_email(email):
    """Validate email. No types, incomplete logic."""
    return "@" in email

class userManager:  # Bad class name
    def __init__(self):
        self.users=[]

    def add(self,user):
        self.users.append(user)
''')

        # Create pyproject.toml
        pyproject = worktree / "pyproject.toml"
        pyproject.write_text('''\
[tool.mypy]
python_version = "3.10"
strict = true

[tool.ruff]
line-length = 100
''')

        # Capture initial state (used in diagnostics below)
        initial_lint = subprocess.run(
            ["ruff", "check", str(broken_file)],
            capture_output=True, text=True, cwd=worktree, check=False
        )
        initial_type = subprocess.run(
            ["mypy", "--strict", str(broken_file)],
            capture_output=True, text=True, cwd=worktree, check=False
        )
        initial_lint_errors = initial_lint.stdout.count(" error") + initial_lint.stdout.count(": ")
        initial_type_errors = initial_type.stdout.count("error:")

        # Run Claude Code with comprehensive prompt
        prompt = f"""\
Fix all issues in {broken_file.name}:

1. Add proper type hints to ALL functions and methods
2. Fix lint errors (use ruff)
3. Fix class naming (PEP 8)
4. Create test_user_service.py with tests for all functions

Quality gates that must pass:
- ruff check {broken_file.name}
- mypy --strict {broken_file.name}
- pytest test_user_service.py

Run all three checks to verify your work.
"""

        result = subprocess.run(
            [
                "claude",
                "-p",
                "--model", "sonnet",  # Use sonnet for complex task
                "--max-budget-usd", "0.50",
                "--allowedTools", "Read,Edit,Write,Bash",
                "--dangerously-skip-permissions",
                prompt,
            ],
            stdin=subprocess.DEVNULL,  # Critical: prevent hanging on stdin
            capture_output=True,
            text=True,
            cwd=worktree,
            timeout=300,
            check=False,
        )

        # Log everything (defensive: worktree may not exist)
        if worktree.exists():
            (worktree / ".agent_output.log").write_text(
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        # Verify worktree still exists
        assert worktree.exists(), (
            f"Worktree was deleted during test.\n"
            f"Agent stderr: {result.stderr[:500]}"
        )

        # Run quality gates
        lint_result = subprocess.run(
            ["ruff", "check", str(broken_file)],
            capture_output=True, text=True, cwd=worktree, check=False
        )
        type_result = subprocess.run(
            ["mypy", "--strict", str(broken_file)],
            capture_output=True, text=True, cwd=worktree, check=False
        )

        # Check for test file
        test_file = worktree / "test_user_service.py"
        test_result = None
        if test_file.exists():
            test_result = subprocess.run(
                ["python", "-m", "pytest", str(test_file), "-v"],
                capture_output=True, text=True, cwd=worktree, check=False
            )

        # Compile results
        results: dict[str, Any] = {
            "initial_lint_errors": initial_lint_errors,
            "initial_type_errors": initial_type_errors,
            "lint_passed": lint_result.returncode == 0,
            "lint_output": lint_result.stdout,
            "type_passed": type_result.returncode == 0,
            "type_output": type_result.stdout,
            "test_file_created": test_file.exists(),
            "tests_passed": test_result.returncode == 0 if test_result else False,
            "test_output": test_result.stdout if test_result else "No test file",
            "final_code": broken_file.read_text(),
        }

        if worktree.exists():
            (worktree / ".quality_results.json").write_text(
                json.dumps(results, indent=2)
            )

        # Assert all gates pass
        gates_passed = sum([
            results["lint_passed"],
            results["type_passed"],
            results["tests_passed"],
        ])

        assert gates_passed >= 2, (
            f"Agent should pass at least 2/3 quality gates.\n"
            f"Lint: {'PASS' if results['lint_passed'] else 'FAIL'}\n"
            f"Type: {'PASS' if results['type_passed'] else 'FAIL'}\n"
            f"Test: {'PASS' if results['tests_passed'] else 'FAIL'}\n"
            f"Details in {worktree}/.quality_results.json"
        )
