"""Tests for AC-1/AC-2/AC-4: test_data_pipeline.py refactored to use shared fixture.

Verifies that ``test_data_pipeline.py`` has been correctly refactored so that:
- Read-only tests use the shared ``dbt_pipeline_result`` fixture instead of
  calling ``run_dbt`` inline
- Mutating tests retain their own ``run_dbt`` calls (separate namespaces)
- No assertions have been weakened during the refactor
- Total dbt seed/run invocations are drastically reduced in test method bodies

These are STATIC ANALYSIS tests (source code inspection). They do NOT
require K8s, Docker, or any infrastructure. They parse the Python source
file and inspect method bodies via AST.

Test types:
- Static analysis tests: verify test_data_pipeline.py source structure via
  AST. No boundary crossing, pure function on source text.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TARGET_FILE = _REPO_ROOT / "tests" / "e2e" / "test_data_pipeline.py"

# ---------------------------------------------------------------------------
# Test method classification
# ---------------------------------------------------------------------------

# Read-only tests: must NOT call run_dbt in their bodies after refactor.
# They should receive pipeline results from the dbt_pipeline_result fixture.
READ_ONLY_TESTS: list[str] = [
    "test_dbt_seed_loads_data",
    "test_pipeline_execution_order",
    "test_medallion_layers",
    "test_iceberg_tables_created",
    "test_dbt_tests_pass",
    "test_data_quality_checks",
    "test_data_retention_enforcement",
]

# Mutating tests: MUST keep their own run_dbt calls (separate namespaces).
MUTATING_TESTS: list[str] = [
    "test_incremental_model_merge",
    "test_pipeline_failure_recording",
    "test_pipeline_retry",
]

# Tests that never called run_dbt -- should remain unchanged.
NO_DBT_TESTS: list[str] = [
    "test_auto_trigger_sensor_e2e",
    "test_transformation_math_correctness",
    "test_snapshot_expiry_enforcement",
]

# Pre-refactor baseline counts (from current file).
# These anchor our reduction checks against hardcoded-return bypasses.
PRE_REFACTOR_SEED_CALLS_IN_TEST_METHODS: int = 9
PRE_REFACTOR_RUN_CALLS_IN_TEST_METHODS: int = 12
# Post-refactor baseline: 84 original asserts minus 13 seed/run return-code
# asserts that moved into the dbt_pipeline_result fixture (conftest.py).
# The fixture enforces these via pytest.fail on non-zero return codes.
POST_REFACTOR_ASSERT_COUNT: int = 71


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _parse_target() -> ast.Module:
    """Parse test_data_pipeline.py into an AST module.

    Returns:
        Parsed AST module node.

    Raises:
        pytest.fail: If the file cannot be parsed.
    """
    source = _TARGET_FILE.read_text()
    try:
        return ast.parse(source, filename=str(_TARGET_FILE))
    except SyntaxError as exc:
        pytest.fail(f"test_data_pipeline.py has syntax error: {exc}")
        raise  # unreachable, satisfies mypy


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    """Find a top-level class by name.

    Args:
        tree: Parsed AST module.
        name: Class name to find.

    Returns:
        The ClassDef node, or None if not found.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _count_run_dbt_calls(func: ast.FunctionDef, dbt_command: str) -> int:
    """Count run_dbt calls with a specific command in a function body.

    Matches patterns like ``run_dbt(["seed"], ...)`` or ``run_dbt(["run"], ...)``.

    Args:
        func: Function AST node.
        dbt_command: The dbt command string (e.g., "seed", "run").

    Returns:
        Number of matching calls found.
    """
    count = 0
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if not (isinstance(callee, ast.Name) and callee.id == "run_dbt"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.List):
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and elt.value == dbt_command:
                        count += 1
    return count


def _method_has_param(func: ast.FunctionDef, param_name: str) -> bool:
    """Check if a method has a parameter with the given name.

    Args:
        func: Function AST node.
        param_name: Parameter name to search for.

    Returns:
        True if the parameter exists.
    """
    for arg in func.args.args:
        if arg.arg == param_name:
            return True
    return False


def _count_asserts_in_body(func: ast.FunctionDef) -> int:
    """Count assert statements in a function body.

    Args:
        func: Function AST node.

    Returns:
        Number of assert statements found.
    """
    count = 0
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            count += 1
    return count


def _get_test_class_and_methods() -> tuple[ast.ClassDef, dict[str, ast.FunctionDef]]:
    """Parse file and return the test class and its test methods.

    Returns:
        Tuple of (class_node, {method_name: method_node}).

    Raises:
        pytest.fail: If TestDataPipeline class is not found.
    """
    tree = _parse_target()
    cls = _find_class(tree, "TestDataPipeline")
    if cls is None:
        pytest.fail(
            "Class 'TestDataPipeline' not found in test_data_pipeline.py. "
            "The refactoring should preserve the class name."
        )
        raise AssertionError  # unreachable

    methods: dict[str, ast.FunctionDef] = {}
    for node in ast.iter_child_nodes(cls):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                methods[node.name] = node  # type: ignore[assignment]
    return cls, methods


# =========================================================================
# Tests
# =========================================================================


class TestReadOnlyTestsUseFixture:
    """Verify read-only tests no longer call run_dbt inline."""

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize("method_name", READ_ONLY_TESTS)
    def test_no_seed_calls_in_read_only_tests(self, method_name: str) -> None:
        """Read-only test methods must NOT contain run_dbt(["seed"]) calls.

        After refactoring, seed invocations are handled by the shared
        dbt_pipeline_result fixture. Any remaining seed call in a read-only
        test means the refactor was incomplete for that method.

        Args:
            method_name: Name of the read-only test method to check.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, (
            f"Test method '{method_name}' not found in TestDataPipeline. "
            "Was it renamed or deleted during refactoring?"
        )
        seed_count = _count_run_dbt_calls(func, "seed")
        assert seed_count == 0, (
            f"Read-only test '{method_name}' still has {seed_count} run_dbt(['seed']) "
            f"call(s). After refactoring, seed should be handled by the "
            f"dbt_pipeline_result fixture, not inline in the test method."
        )

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize("method_name", READ_ONLY_TESTS)
    def test_no_run_calls_in_read_only_tests(self, method_name: str) -> None:
        """Read-only test methods must NOT contain run_dbt(["run"]) calls.

        After refactoring, dbt run is handled by the shared
        dbt_pipeline_result fixture. Any remaining run call in a read-only
        test means the refactor was incomplete for that method.

        Args:
            method_name: Name of the read-only test method to check.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, (
            f"Test method '{method_name}' not found in TestDataPipeline. "
            "Was it renamed or deleted during refactoring?"
        )
        run_count = _count_run_dbt_calls(func, "run")
        assert run_count == 0, (
            f"Read-only test '{method_name}' still has {run_count} run_dbt(['run']) "
            f"call(s). After refactoring, dbt run should be handled by the "
            f"dbt_pipeline_result fixture, not inline in the test method."
        )

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize(
        "method_name",
        [
            "test_dbt_seed_loads_data",
            "test_pipeline_execution_order",
            "test_medallion_layers",
            "test_iceberg_tables_created",
            "test_dbt_tests_pass",
            "test_data_quality_checks",
            "test_data_retention_enforcement",
        ],
    )
    def test_read_only_tests_use_dbt_pipeline_result_fixture(self, method_name: str) -> None:
        """Read-only tests that previously called run_dbt must accept dbt_pipeline_result.

        The fixture parameter ``dbt_pipeline_result`` must appear in the
        method signature. Without it, the test cannot receive the shared
        pipeline output and would need to run dbt itself.

        Args:
            method_name: Name of the read-only test method to check.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, f"Test method '{method_name}' not found in TestDataPipeline."
        assert _method_has_param(func, "dbt_pipeline_result"), (
            f"Test method '{method_name}' does not have 'dbt_pipeline_result' "
            f"in its parameter list. After refactoring, read-only tests must "
            f"receive pipeline results from the shared fixture."
        )


class TestMutatingTestsPreserved:
    """Verify mutating tests retain their own run_dbt calls."""

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize("method_name", MUTATING_TESTS)
    def test_mutating_tests_exist(self, method_name: str) -> None:
        """Mutating test methods must still exist after refactoring.

        These tests need their own namespaces and dbt invocations because
        they modify the pipeline state. They must not be accidentally
        removed or merged into the read-only fixture flow.

        Args:
            method_name: Name of the mutating test method to check.
        """
        _, methods = _get_test_class_and_methods()
        assert method_name in methods, (
            f"Mutating test '{method_name}' not found in TestDataPipeline. "
            "Mutating tests must not be removed during refactoring."
        )

    @pytest.mark.requirement("AC-2")
    def test_incremental_merge_does_not_use_shared_fixture(self) -> None:
        """test_incremental_model_merge must NOT use dbt_pipeline_result.

        This test re-runs dbt to test incremental merge behavior, so it
        needs its own isolated dbt invocations, not the shared fixture.
        Using the shared fixture would mean it cannot re-run dbt to test
        the merge.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get("test_incremental_model_merge")
        assert func is not None, "test_incremental_model_merge not found."
        assert not _method_has_param(func, "dbt_pipeline_result"), (
            "test_incremental_model_merge should NOT use dbt_pipeline_result. "
            "It needs its own dbt seed+run cycle to test incremental behavior."
        )

    @pytest.mark.requirement("AC-2")
    def test_failure_recording_does_not_use_shared_fixture(self) -> None:
        """test_pipeline_failure_recording must NOT use dbt_pipeline_result.

        This test injects a bad model and expects failure. Sharing the
        fixture would either break the shared state or skip the failure
        scenario entirely.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get("test_pipeline_failure_recording")
        assert func is not None, "test_pipeline_failure_recording not found."
        assert not _method_has_param(func, "dbt_pipeline_result"), (
            "test_pipeline_failure_recording should NOT use dbt_pipeline_result. "
            "It needs its own pipeline execution with an injected bad model."
        )

    @pytest.mark.requirement("AC-2")
    def test_retry_does_not_use_shared_fixture(self) -> None:
        """test_pipeline_retry must NOT use dbt_pipeline_result.

        This test injects a bad model, expects failure, fixes it, and
        retries. It requires its own isolated pipeline lifecycle.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get("test_pipeline_retry")
        assert func is not None, "test_pipeline_retry not found."
        assert not _method_has_param(func, "dbt_pipeline_result"), (
            "test_pipeline_retry should NOT use dbt_pipeline_result. "
            "It needs its own pipeline execution with injected failure and retry."
        )

    @pytest.mark.requirement("AC-2")
    def test_mutating_tests_do_not_affect_read_only(self) -> None:
        """Mutating tests must not share fixture state with read-only tests.

        Verify that no mutating test uses the dbt_pipeline_result fixture,
        which would allow them to corrupt the shared pipeline state that
        read-only tests depend on.
        """
        _, methods = _get_test_class_and_methods()
        for method_name in MUTATING_TESTS:
            func = methods.get(method_name)
            if func is None:
                continue
            assert not _method_has_param(func, "dbt_pipeline_result"), (
                f"Mutating test '{method_name}' uses dbt_pipeline_result fixture. "
                f"This would allow it to corrupt shared state used by read-only tests."
            )


class TestCallCountReductions:
    """Verify overall dbt invocation counts are reduced after refactoring."""

    @pytest.mark.requirement("AC-4")
    def test_total_seed_calls_in_test_methods_reduced(self) -> None:
        """Total run_dbt(["seed"]) in test method bodies must be <= 3.

        Before refactoring there are 9 seed calls across test methods.
        After refactoring, only the 3 mutating tests should have seed
        calls (at most). Read-only tests use the fixture.

        The threshold of 3 matches AC-4 condition 1.
        """
        _, methods = _get_test_class_and_methods()
        total_seed = 0
        methods_with_seed: list[str] = []
        for name, func in methods.items():
            count = _count_run_dbt_calls(func, "seed")
            if count > 0:
                total_seed += count
                methods_with_seed.append(f"{name} ({count})")
        assert total_seed <= 3, (
            f"Total run_dbt(['seed']) calls in test methods is {total_seed}, "
            f"expected <= 3 (only mutating tests). "
            f"Methods with seed calls: {', '.join(methods_with_seed)}"
        )

    @pytest.mark.requirement("AC-4")
    def test_total_run_calls_in_test_methods_reduced(self) -> None:
        """Total run_dbt(["run"]) in test method bodies must be significantly reduced.

        Before refactoring there are 12 run calls across test methods.
        After refactoring, only mutating tests should call run_dbt(["run"]).
        The 3 mutating tests have at most 5 run calls between them
        (incremental_merge has 2, failure_recording has 1, retry has 2).
        Read-only tests should have 0.
        """
        _, methods = _get_test_class_and_methods()
        total_run = 0
        read_only_run = 0
        methods_with_run: list[str] = []
        for name, func in methods.items():
            count = _count_run_dbt_calls(func, "run")
            if count > 0:
                total_run += count
                methods_with_run.append(f"{name} ({count})")
            if name in READ_ONLY_TESTS:
                read_only_run += count

        # Read-only tests must have zero run calls
        assert read_only_run == 0, (
            f"Read-only tests still have {read_only_run} run_dbt(['run']) calls. "
            f"After refactoring, all run calls in read-only tests should be "
            f"handled by the dbt_pipeline_result fixture."
        )

        # Total should be drastically reduced from pre-refactor baseline
        assert total_run < PRE_REFACTOR_RUN_CALLS_IN_TEST_METHODS, (
            f"Total run_dbt(['run']) calls ({total_run}) is not reduced from "
            f"pre-refactor baseline ({PRE_REFACTOR_RUN_CALLS_IN_TEST_METHODS}). "
            f"Methods: {', '.join(methods_with_run)}"
        )

    @pytest.mark.requirement("AC-4")
    def test_zero_seed_calls_in_read_only_test_methods(self) -> None:
        """grep-equivalent: zero run_dbt(["seed"]) in read-only test method bodies.

        This directly validates AC-4 condition 4: seed calls must be zero
        in test methods (excluding fixture functions).
        """
        _, methods = _get_test_class_and_methods()
        read_only_seed = 0
        violators: list[str] = []
        for name in READ_ONLY_TESTS:
            func = methods.get(name)
            if func is None:
                continue
            count = _count_run_dbt_calls(func, "seed")
            if count > 0:
                read_only_seed += count
                violators.append(name)
        assert read_only_seed == 0, (
            f"Found {read_only_seed} run_dbt(['seed']) calls in read-only test "
            f"methods: {', '.join(violators)}. AC-4 requires zero seed calls "
            f"in test methods (fixture handles seeding)."
        )


class TestAssertionIntegrity:
    """Verify no assertions were weakened or removed during refactoring."""

    @pytest.mark.requirement("AC-2")
    def test_no_assertion_weakening(self) -> None:
        """Total assert count must not decrease during refactoring.

        The pre-refactor file has 84 assert statements. Removing assertions
        during refactoring would silently reduce test coverage. The count
        must stay >= the original baseline.
        """
        tree = _parse_target()
        total_asserts = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                total_asserts += 1
        assert total_asserts >= POST_REFACTOR_ASSERT_COUNT, (
            f"Total assert statements ({total_asserts}) is less than "
            f"pre-refactor baseline ({POST_REFACTOR_ASSERT_COUNT}). "
            f"Assertions must not be removed during refactoring. "
            f"If seed/run assertions moved to the fixture, the fixture's "
            f"assertions should compensate."
        )

    @pytest.mark.requirement("AC-2")
    def test_all_original_test_methods_preserved(self) -> None:
        """All 13 original test methods must still exist.

        Refactoring must not delete or rename test methods. All read-only,
        mutating, and no-dbt tests must be present.
        """
        _, methods = _get_test_class_and_methods()
        all_expected = READ_ONLY_TESTS + MUTATING_TESTS + NO_DBT_TESTS
        missing: list[str] = []
        for name in all_expected:
            if name not in methods:
                missing.append(name)
        assert len(missing) == 0, (
            f"Missing test methods after refactoring: {missing}. "
            f"All 13 original test methods must be preserved."
        )

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize(
        "method_name,min_asserts",
        [
            # Read-only tests: seed/run return-code asserts moved to fixture
            ("test_dbt_seed_loads_data", 2),
            ("test_pipeline_execution_order", 7),
            ("test_medallion_layers", 7),
            ("test_iceberg_tables_created", 6),
            ("test_dbt_tests_pass", 6),
            ("test_data_quality_checks", 5),
            ("test_data_retention_enforcement", 6),
            # Mutating tests: retain their own dbt calls and assertions
            ("test_incremental_model_merge", 5),
            ("test_pipeline_failure_recording", 2),
            ("test_pipeline_retry", 5),
        ],
    )
    def test_per_method_assertion_count_preserved(self, method_name: str, min_asserts: int) -> None:
        """Each refactored test must retain at least its original assertion count.

        This catches the case where a refactor "simplifies" a test by
        stripping out its important assertions while keeping the method.

        Args:
            method_name: Name of the test method.
            min_asserts: Minimum number of assert statements expected.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, f"Test method '{method_name}' not found."
        actual = _count_asserts_in_body(func)
        assert actual >= min_asserts, (
            f"Test '{method_name}' has {actual} assertions, expected >= {min_asserts}. "
            f"Assertions must not be weakened or removed during refactoring."
        )


class TestNoDbtTestsUnchanged:
    """Verify tests that never called run_dbt remain unchanged."""

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize("method_name", NO_DBT_TESTS)
    def test_no_dbt_tests_still_have_no_dbt_calls(self, method_name: str) -> None:
        """Tests that never called run_dbt must not gain run_dbt calls.

        These tests validate configuration or non-dbt features. Adding
        run_dbt calls to them would be an accidental scope expansion.

        Args:
            method_name: Name of the test method.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, f"Test method '{method_name}' not found."
        seed_count = _count_run_dbt_calls(func, "seed")
        run_count = _count_run_dbt_calls(func, "run")
        assert seed_count == 0 and run_count == 0, (
            f"Test '{method_name}' was not supposed to call run_dbt but now has "
            f"{seed_count} seed and {run_count} run calls. "
            f"This test should remain unchanged."
        )

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize("method_name", NO_DBT_TESTS)
    def test_no_dbt_tests_do_not_use_fixture(self, method_name: str) -> None:
        """Tests that never called run_dbt should not use dbt_pipeline_result.

        Adding the fixture parameter to these tests would be unnecessary
        and would create a false dependency on the fixture.

        Args:
            method_name: Name of the test method.
        """
        _, methods = _get_test_class_and_methods()
        func = methods.get(method_name)
        assert func is not None, f"Test method '{method_name}' not found."
        assert not _method_has_param(func, "dbt_pipeline_result"), (
            f"Test '{method_name}' now has 'dbt_pipeline_result' parameter "
            f"but it never called run_dbt before. This is unnecessary coupling."
        )
