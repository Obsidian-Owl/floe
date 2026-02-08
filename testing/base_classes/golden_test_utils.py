"""Golden test utilities for behavior-preserving refactoring validation.

This module provides utilities for capturing and comparing function outputs
against golden fixtures, enabling safe refactoring with behavioral verification.

Golden tests work by:
1. Capturing the exact output of a function before refactoring
2. Storing that output as a "golden" fixture
3. After refactoring, comparing the new output against the fixture
4. Failing if there are any differences (behavior changed)

Example:
    # Before refactoring: capture golden output
    from testing.base_classes.golden_test_utils import capture_golden, GoldenFixture

    fixture = capture_golden(
        func=my_function,
        args={"param1": "value1"},
        name="my_function_basic_case"
    )
    fixture.save("testing/fixtures/golden/my_module/my_function_basic.json")

    # After refactoring: verify output matches
    from testing.base_classes.golden_test_utils import assert_golden_match

    result = my_function(param1="value1")
    assert_golden_match(result, "testing/fixtures/golden/my_module/my_function_basic.json")
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


@dataclass
class GoldenFixture:
    """Represents a golden test fixture with metadata.

    Attributes:
        name: Human-readable name for this fixture
        output: The captured output (can be any JSON-serializable value)
        captured_at: ISO timestamp when the output was captured
        function_name: Name of the function that produced the output
        args: Arguments passed to the function
        kwargs: Keyword arguments passed to the function
        checksum: SHA256 checksum of the output for integrity verification
    """

    name: str
    output: Any
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    function_name: str = ""
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def __post_init__(self) -> None:
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate SHA256 checksum of the output."""
        output_json = json.dumps(self.output, sort_keys=True, default=str)
        return hashlib.sha256(output_json.encode()).hexdigest()[:16]

    def save(self, path: str | Path) -> Path:
        """Save the fixture to a JSON file.

        Args:
            path: Path to save the fixture (will be created if parent dirs don't exist)

        Returns:
            The path where the fixture was saved
        """
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "function_name": self.function_name,
            "captured_at": self.captured_at,
            "checksum": self.checksum,
            "args": list(self.args) if self.args else [],
            "kwargs": self.kwargs,
            "output": self.output,
        }

        filepath.write_text(json.dumps(data, indent=2, default=str))
        return filepath

    @classmethod
    def load(cls, path: str | Path) -> GoldenFixture:
        """Load a fixture from a JSON file.

        Args:
            path: Path to the fixture file

        Returns:
            GoldenFixture loaded from the file

        Raises:
            FileNotFoundError: If the fixture file doesn't exist
            ValueError: If the fixture file is invalid
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Golden fixture not found: {filepath}")

        try:
            data = json.loads(filepath.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in golden fixture: {filepath}") from e

        return cls(
            name=data["name"],
            output=data["output"],
            captured_at=data.get("captured_at", ""),
            function_name=data.get("function_name", ""),
            args=tuple(data.get("args", [])),
            kwargs=data.get("kwargs", {}),
            checksum=data.get("checksum", ""),
        )

    def verify_integrity(self) -> bool:
        """Verify the fixture's checksum matches its output.

        Returns:
            True if checksum matches, False otherwise
        """
        return self.checksum == self._calculate_checksum()


def capture_golden(
    func: Callable[..., Any],
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    name: str = "",
) -> GoldenFixture:
    """Capture the output of a function as a golden fixture.

    Use this to create golden fixtures before refactoring.

    Args:
        func: The function to call and capture output from
        args: Positional arguments to pass to the function
        kwargs: Keyword arguments to pass to the function
        name: Human-readable name for the fixture

    Returns:
        GoldenFixture containing the captured output

    Example:
        fixture = capture_golden(
            my_complex_function,
            args=(arg1, arg2),
            kwargs={"option": True},
            name="complex_function_with_option"
        )
        fixture.save("testing/fixtures/golden/my_module/complex_with_option.json")
    """
    args = args or ()
    kwargs = kwargs or {}
    output = func(*args, **kwargs)

    return GoldenFixture(
        name=name or func.__name__,
        output=output,
        function_name=func.__name__,
        args=args,
        kwargs=kwargs,
    )


def assert_golden_match(
    actual: Any,
    fixture_path: str | Path,
    *,
    update: bool = False,
    message: str = "",
) -> None:
    """Assert that actual output matches the golden fixture.

    Use this after refactoring to verify behavior is preserved.

    Args:
        actual: The actual output to compare
        fixture_path: Path to the golden fixture file
        update: If True, update the fixture with actual output instead of failing
        message: Additional message to include in failure output

    Raises:
        AssertionError: If outputs don't match (and update=False)
        FileNotFoundError: If fixture doesn't exist (and update=False)

    Example:
        result = my_refactored_function(arg1, arg2, option=True)
        assert_golden_match(result, "testing/fixtures/golden/my_module/complex.json")
    """
    path = Path(fixture_path)

    if update:
        # Update mode: save actual output as new golden fixture
        fixture = GoldenFixture(
            name=path.stem,
            output=actual,
        )
        fixture.save(path)
        return

    # Load expected fixture
    try:
        expected_fixture = GoldenFixture.load(path)
    except FileNotFoundError:
        pytest.fail(
            f"Golden fixture not found: {path}\n"
            f"Run with update=True to create it, or use capture_golden() to create manually."
        )

    # Verify fixture integrity
    if not expected_fixture.verify_integrity():
        pytest.fail(
            f"Golden fixture integrity check failed: {path}\n"
            f"The fixture may have been corrupted. Re-capture with capture_golden()."
        )

    # Compare outputs
    if actual != expected_fixture.output:
        # Generate diff for debugging
        actual_json = json.dumps(actual, indent=2, sort_keys=True, default=str)
        expected_json = json.dumps(
            expected_fixture.output, indent=2, sort_keys=True, default=str
        )

        diff_msg = (
            f"Golden test failed: output does not match fixture\nFixture: {path}\n"
        )
        if message:
            diff_msg += f"Context: {message}\n"
        diff_msg += f"\nExpected:\n{expected_json}\n\nActual:\n{actual_json}"

        pytest.fail(diff_msg)


def golden_test(
    fixture_path: str | Path,
) -> Callable[[Callable[..., Any]], Callable[..., None]]:
    """Decorator for creating golden tests.

    The decorated function should return the output to compare against the fixture.

    Args:
        fixture_path: Path to the golden fixture file

    Returns:
        Decorator function

    Example:
        @golden_test("testing/fixtures/golden/my_module/test_case.json")
        def test_my_function():
            return my_function(arg1, arg2)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., None]:
        def wrapper() -> None:
            result = func()
            assert_golden_match(result, fixture_path)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


class GoldenTestCase:
    """Base class for golden test suites.

    Provides fixtures_dir property and helper methods for managing golden tests.

    Example:
        class TestDiffCommand(GoldenTestCase):
            fixtures_dir = Path("testing/fixtures/golden/cli_rbac/diff_command")

            def test_basic_diff(self):
                result = diff_command(old_spec, new_spec)
                self.assert_golden("basic_diff.json", result)
    """

    fixtures_dir: Path = Path("testing/fixtures/golden")

    def assert_golden(
        self, fixture_name: str, actual: Any, *, update: bool = False
    ) -> None:
        """Assert actual output matches named golden fixture.

        Args:
            fixture_name: Name of the fixture file (relative to fixtures_dir)
            actual: The actual output to compare
            update: If True, update the fixture instead of failing
        """
        fixture_path = self.fixtures_dir / fixture_name
        assert_golden_match(actual, fixture_path, update=update)

    def capture_golden_fixture(
        self,
        fixture_name: str,
        func: Callable[..., Any],
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> GoldenFixture:
        """Capture and save a golden fixture.

        Args:
            fixture_name: Name of the fixture file (relative to fixtures_dir)
            func: Function to capture output from
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function

        Returns:
            The captured fixture
        """
        fixture = capture_golden(func, args=args, kwargs=kwargs, name=fixture_name)
        fixture.save(self.fixtures_dir / fixture_name)
        return fixture
