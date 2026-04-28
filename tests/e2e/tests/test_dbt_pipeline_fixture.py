"""Tests for AC-1: dbt_pipeline_result module-scoped fixture in conftest.py.

Verifies that tests/e2e/conftest.py contains a ``dbt_pipeline_result``
fixture with the correct structural properties:
- Module scope for isolation
- Runs dbt seed then dbt run
- Uses a unique namespace suffix to prevent cross-module pollution
- Yields a result tuple
- Cleans up in a finally block

These are STATIC ANALYSIS tests (AST parsing) -- they do NOT require K8s.
All tests must FAIL before implementation because the fixture does not
exist yet.

Test types:
- Static analysis tests: verify conftest.py source structure via AST.
  No boundary crossing, pure function on source text.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = pytest.mark.developer_workflow

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFTEST_PATH = _REPO_ROOT / "tests" / "e2e" / "conftest.py"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _parse_conftest() -> ast.Module:
    """Parse conftest.py into an AST module.

    Returns:
        Parsed AST module node.

    Raises:
        pytest.fail: If conftest.py cannot be parsed.
    """
    source = _CONFTEST_PATH.read_text()
    try:
        return ast.parse(source, filename=str(_CONFTEST_PATH))
    except SyntaxError as exc:
        pytest.fail(f"conftest.py has syntax error: {exc}")
        raise  # unreachable, satisfies mypy


def _load_runtime_conftest_module() -> Any:
    """Load tests/e2e/conftest.py as a standalone module for runtime tests."""
    spec = importlib.util.spec_from_file_location("floe_e2e_conftest_runtime", _CONFTEST_PATH)
    assert spec is not None, "Could not create import spec for tests/e2e/conftest.py"
    assert spec.loader is not None, "Could not load tests/e2e/conftest.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runtime_dbt_utils_module() -> Any:
    """Load tests/e2e/dbt_utils.py as a standalone module for runtime tests."""
    dbt_utils_path = _REPO_ROOT / "tests" / "e2e" / "dbt_utils.py"
    spec = importlib.util.spec_from_file_location("floe_e2e_dbt_utils_runtime", dbt_utils_path)
    assert spec is not None, "Could not create import spec for tests/e2e/dbt_utils.py"
    assert spec.loader is not None, "Could not load tests/e2e/dbt_utils.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_function_def(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    """Find a top-level FunctionDef or AsyncFunctionDef by name.

    Args:
        tree: Parsed AST module.
        name: Function name to find.

    Returns:
        The function AST node, or None if not found.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node  # type: ignore[return-value]
    return None


def _get_fixture_decorator(
    func: ast.FunctionDef,
) -> ast.Call | None:
    """Extract the @pytest.fixture(...) call node from a function's decorators.

    Args:
        func: Function AST node.

    Returns:
        The Call node for the pytest.fixture decorator, or None.
    """
    for dec in func.decorator_list:
        # @pytest.fixture(scope="module")  -- Call node
        if isinstance(dec, ast.Call):
            callee = dec.func
            if isinstance(callee, ast.Attribute) and callee.attr == "fixture":
                return dec
        # @pytest.fixture  -- bare Attribute (no args)
        if isinstance(dec, ast.Attribute) and dec.attr == "fixture":
            return None  # decorator exists but no Call args
    return None


def _has_fixture_decorator(func: ast.FunctionDef) -> bool:
    """Check whether a function has any form of @pytest.fixture decorator.

    Args:
        func: Function AST node.

    Returns:
        True if the function has a pytest.fixture decorator.
    """
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call):
            callee = dec.func
            if isinstance(callee, ast.Attribute) and callee.attr == "fixture":
                return True
        if isinstance(dec, ast.Attribute) and dec.attr == "fixture":
            return True
    return False


def _get_fixture_scope(call: ast.Call) -> str | None:
    """Extract the scope keyword argument value from a pytest.fixture call.

    Args:
        call: The Call AST node for @pytest.fixture(...).

    Returns:
        The scope string value, or None if not specified.
    """
    for kw in call.keywords:
        if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    # Also check positional: pytest.fixture("module") is valid but unusual
    if call.args and isinstance(call.args[0], ast.Constant):
        return str(call.args[0].value)
    return None


def _body_contains_string_in_call(func: ast.FunctionDef, func_name: str, string_arg: str) -> bool:
    """Check if function body contains a call to func_name with string_arg.

    Searches for patterns like: run_dbt(["seed", ...], ...) or
    run_dbt(["run", ...], ...) where the first list element matches.

    Args:
        func: Function AST node.
        func_name: Name of the called function (e.g., "run_dbt").
        string_arg: String that must appear in a list argument
                     (e.g., "seed" or "run").

    Returns:
        True if a matching call pattern is found.
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        # Match direct call: run_dbt(...)
        callee = node.func
        if isinstance(callee, ast.Name) and callee.id == func_name:
            # Check if any argument is a list containing string_arg
            for arg in node.args:
                if isinstance(arg, ast.List):
                    for elt in arg.elts:
                        if isinstance(elt, ast.Constant) and elt.value == string_arg:
                            return True
                # Also handle bare string arg: run_dbt("seed", ...)
                if isinstance(arg, ast.Constant) and arg.value == string_arg:
                    return True
    return False


def _function_has_yield(func: ast.FunctionDef) -> bool:
    """Check if a function body contains a Yield or YieldFrom node.

    Args:
        func: Function AST node.

    Returns:
        True if the function yields.
    """
    for node in ast.walk(func):
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def _function_has_try_finally(func: ast.FunctionDef) -> bool:
    """Check if a function body contains a Try node with a finalbody.

    Args:
        func: Function AST node.

    Returns:
        True if a try/finally block is present.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Try) and node.finalbody:
            return True
    return False


def _finally_calls_function(func: ast.FunctionDef, callee_name: str) -> bool:
    """Check if the finally block of a try/finally calls a specific function.

    Args:
        func: Function AST node.
        callee_name: Name of function expected in finally block.

    Returns:
        True if the finally block calls callee_name.
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Try) or not node.finalbody:
            continue
        for finally_node in ast.walk(ast.Module(body=node.finalbody, type_ignores=[])):
            if isinstance(finally_node, ast.Call):
                callee = finally_node.func
                if isinstance(callee, ast.Name) and callee.id == callee_name:
                    return True
                if isinstance(callee, ast.Attribute) and callee.attr == callee_name:
                    return True
    return False


def _collect_purge_calls(
    statements: list[ast.stmt],
) -> list[ast.Call]:
    """Collect _purge_iceberg_namespace calls from a statement list."""
    calls: list[ast.Call] = []
    for node in ast.walk(ast.Module(body=statements, type_ignores=[])):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name) and callee.id == "_purge_iceberg_namespace":
            calls.append(node)
    return calls


def _call_has_keyword_bool(call: ast.Call, keyword: str, value: bool) -> bool:
    """Return whether a call sets a bool keyword to the expected value."""
    for kw in call.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant) and kw.value.value is value:
            return True
    return False


# =========================================================================
# Tests
# =========================================================================


class TestDbtPipelineResultFixtureStructure:
    """Verify dbt_pipeline_result fixture exists with correct AST structure."""

    @pytest.mark.requirement("AC-1")
    def test_dbt_pipeline_result_fixture_exists(self) -> None:
        """dbt_pipeline_result must be defined in conftest.py with @pytest.fixture.

        A fixture by this exact name must exist so that E2E test modules can
        request it via indirect parametrize. Without it, tests cannot run
        dbt pipelines in a module-isolated way.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, (
            "Function 'dbt_pipeline_result' not found in tests/e2e/conftest.py. "
            "AC-1 requires this fixture for module-scoped dbt pipeline execution."
        )
        assert _has_fixture_decorator(func), (
            "'dbt_pipeline_result' exists but lacks @pytest.fixture decorator. "
            "It must be a pytest fixture to be usable by test modules."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_scope_is_module(self) -> None:
        """dbt_pipeline_result fixture must have scope='module'.

        Module scope ensures the dbt seed+run cycle executes once per test
        module, not once per test function (too slow) or once per session
        (cross-module pollution). This is the key isolation guarantee.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found -- cannot check scope."
        call = _get_fixture_decorator(func)
        assert call is not None, (
            "@pytest.fixture decorator has no arguments -- scope is not set. "
            'Must be @pytest.fixture(scope="module").'
        )
        scope = _get_fixture_scope(call)
        assert scope == "module", (
            f"Fixture scope is {scope!r}, expected 'module'. "
            "Module scope is required for per-module dbt pipeline isolation."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_calls_dbt_seed(self) -> None:
        """dbt_pipeline_result must call run_dbt with 'seed' argument.

        dbt seed must run before dbt run to load reference data into the
        Iceberg namespace. Without this, dbt run will fail on missing sources.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found -- cannot check body."
        assert _body_contains_string_in_call(func, "run_dbt", "seed"), (
            "dbt_pipeline_result does not call run_dbt with 'seed' argument. "
            "The fixture must run dbt seed before dbt run to load reference data."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_calls_dbt_run(self) -> None:
        """dbt_pipeline_result must call run_dbt with 'run' argument.

        dbt run executes the transformation models after seed data is loaded.
        This is the core pipeline execution step.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found -- cannot check body."
        assert _body_contains_string_in_call(func, "run_dbt", "run"), (
            "dbt_pipeline_result does not call run_dbt with 'run' argument. "
            "The fixture must run dbt run to execute transformation models."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_has_yield(self) -> None:
        """dbt_pipeline_result must use yield (generator fixture pattern).

        Yield-based fixtures allow setup (dbt seed + run) before yielding
        and cleanup (namespace purge) after yield. A return-based fixture
        cannot perform cleanup reliably.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, (
            "Function 'dbt_pipeline_result' not found -- cannot check for yield."
        )
        assert _function_has_yield(func), (
            "dbt_pipeline_result does not use 'yield'. "
            "It must be a generator fixture (yield, not return) to support "
            "cleanup in a finally block."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_has_finally_cleanup(self) -> None:
        """dbt_pipeline_result must have a try/finally block for cleanup.

        The finally block ensures Iceberg namespace cleanup runs even when
        dbt seed or dbt run fails, preventing resource leaks that pollute
        subsequent test runs.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found -- cannot check cleanup."
        assert _function_has_try_finally(func), (
            "dbt_pipeline_result does not have a try/finally block. "
            "Cleanup (namespace purge) must run in 'finally' to avoid "
            "resource leaks on test failure."
        )

    @pytest.mark.requirement("AC-1")
    def test_fixture_derives_namespace_from_product(self) -> None:
        """dbt_pipeline_result must derive namespace names from the product.

        Namespace names must match what dbt actually writes to — the
        profile's ``schema: {profile_name}`` and ``+schema: raw`` for
        seeds.  The fixture must use ``_purge_iceberg_namespace`` with
        these derived names so cleanup targets real namespaces.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, (
            "Function 'dbt_pipeline_result' not found -- cannot check namespace."
        )
        source = ast.get_source_segment(_CONFTEST_PATH.read_text(), func)
        assert source is not None, "Cannot extract source for dbt_pipeline_result"

        # Fixture must derive namespace from product name
        assert "product" in source or "product_name" in source, (
            "dbt_pipeline_result does not reference 'product' or 'product_name' "
            "— namespace derivation must be based on the dbt product."
        )
        # Fixture must call _purge_iceberg_namespace for cleanup
        assert "_purge_iceberg_namespace" in source, (
            "dbt_pipeline_result does not call _purge_iceberg_namespace — "
            "Iceberg namespaces must be cleaned up to prevent resource leaks."
        )


class TestDbtPipelineResultFixtureSemantics:
    """Verify semantic properties beyond basic structure.

    These tests catch sloppy implementations that have the right shape
    but wrong ordering or missing cleanup calls.
    """

    @pytest.mark.requirement("AC-1")
    def test_seed_before_run(self) -> None:
        """dbt seed must appear before dbt run in the function body.

        Running dbt run before seed would fail because reference data
        is not yet loaded. The fixture must enforce this ordering.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, (
            "Function 'dbt_pipeline_result' not found -- cannot check ordering."
        )
        # Walk the body linearly (not recursively) to find ordering
        source = ast.get_source_segment(_CONFTEST_PATH.read_text(), func)
        assert source is not None, "Could not extract source for dbt_pipeline_result."

        # Find positions of "seed" and "run" in run_dbt calls
        seed_pos = source.find('"seed"')
        if seed_pos == -1:
            seed_pos = source.find("'seed'")
        run_pos = source.find('"run"')
        if run_pos == -1:
            run_pos = source.find("'run'")

        assert seed_pos != -1, "Could not find 'seed' string in fixture body."
        assert run_pos != -1, "Could not find 'run' string in fixture body."
        assert seed_pos < run_pos, (
            f"'seed' (pos {seed_pos}) appears AFTER 'run' (pos {run_pos}) "
            "in dbt_pipeline_result. dbt seed must execute before dbt run."
        )

    @pytest.mark.requirement("AC-1")
    def test_finally_calls_purge_iceberg_namespace(self) -> None:
        """The finally block must call _purge_iceberg_namespace for cleanup.

        Using a different cleanup function or no cleanup at all would leave
        stale Iceberg namespaces that pollute future test runs.
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, (
            "Function 'dbt_pipeline_result' not found -- cannot check cleanup call."
        )
        assert _finally_calls_function(func, "_purge_iceberg_namespace"), (
            "dbt_pipeline_result finally block does not call "
            "'_purge_iceberg_namespace'. Cleanup must use this function "
            "to properly remove Iceberg tables and namespace."
        )

    @pytest.mark.requirement("AC-1")
    def test_setup_purges_use_verified_reset(self) -> None:
        """Setup purges must verify both raw and model namespaces are empty."""
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found."

        setup_calls: list[ast.Call] = []
        for node in func.body:
            if isinstance(node, ast.Try):
                setup_calls = _collect_purge_calls(node.body)
                break

        assert len(setup_calls) == 2, (
            "dbt_pipeline_result setup must call _purge_iceberg_namespace twice "
            "for raw and model namespaces before running dbt."
        )
        assert all(_call_has_keyword_bool(call, "verify_empty", True) for call in setup_calls), (
            "All setup _purge_iceberg_namespace calls must pass verify_empty=True."
        )

    @pytest.mark.requirement("AC-1")
    def test_teardown_purges_use_verified_reset(self) -> None:
        """Teardown purges must verify both raw and model namespaces are empty."""
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found."

        teardown_calls: list[ast.Call] = []
        for node in func.body:
            if isinstance(node, ast.Try):
                teardown_calls = _collect_purge_calls(node.finalbody)
                break

        assert teardown_calls, (
            "dbt_pipeline_result teardown must call _purge_iceberg_namespace in finally "
            "for raw and model namespace cleanup."
        )
        assert all(_call_has_keyword_bool(call, "verify_empty", True) for call in teardown_calls), (
            "All teardown _purge_iceberg_namespace calls must pass verify_empty=True."
        )

    @pytest.mark.requirement("AC-1")
    def test_yield_inside_try_block(self) -> None:
        """yield must be inside a try block, not outside it.

        If yield is outside try/finally, the cleanup code will not run
        when the test module finishes. The yield must be the boundary
        between setup (try body) and teardown (finally).
        """
        tree = _parse_conftest()
        func = _find_function_def(tree, "dbt_pipeline_result")
        assert func is not None, "Function 'dbt_pipeline_result' not found."
        # Find all try nodes and check if any contain a yield
        yield_in_try = False
        for node in ast.walk(func):
            if isinstance(node, ast.Try):
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.Yield, ast.YieldFrom)):
                        yield_in_try = True
                        break
        assert yield_in_try, (
            "yield is not inside a try block in dbt_pipeline_result. "
            "The yield must be within try so that finally cleanup executes "
            "after the test module completes."
        )

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize("phase", ["setup", "test_body"])
    def test_runtime_teardown_reset_failure_does_not_mask_primary_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        phase: str,
    ) -> None:
        """Teardown reset errors must not replace an earlier dbt or test failure."""
        import dbt_utils

        runtime_conftest = _load_runtime_conftest_module()
        fixture_func = runtime_conftest.dbt_pipeline_result.__wrapped__

        project_root = tmp_path
        project_dir = project_root / "demo" / "customer-360"
        project_dir.mkdir(parents=True)
        request = SimpleNamespace(param="customer-360")
        log_messages: list[str] = []
        purge_calls: list[str] = []

        def _record_error(message: str, *args: object) -> None:
            log_messages.append(message % args if args else message)

        def _purge(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
            del retries
            purge_calls.append(f"{namespace}:{verify_empty}")
            if len(purge_calls) > 2:
                raise dbt_utils.NamespaceResetError(f"teardown failed for {namespace}")

        def _run_dbt(args: list[str], project_dir_arg: Path) -> SimpleNamespace:
            assert project_dir_arg == project_dir
            if phase == "setup" and args == ["seed"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="seed exploded")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(runtime_conftest.logger, "error", _record_error)
        monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _purge)
        monkeypatch.setattr(dbt_utils, "run_dbt", _run_dbt)

        generator = fixture_func(request, project_root, {})

        if phase == "setup":
            with pytest.raises(pytest.fail.Exception, match="dbt seed failed"):
                next(generator)
        else:
            assert next(generator) == ("customer-360", project_dir)
            with pytest.raises(RuntimeError, match="test body failed"):
                generator.throw(RuntimeError("test body failed"))

        assert len(log_messages) == 2, (
            "Teardown NamespaceResetError should be logged for both namespaces "
            "when a primary failure already exists."
        )
        assert all("Suppressed teardown reset failure" in message for message in log_messages), (
            "Suppressed teardown reset failures must be surfaced in logs."
        )
        assert purge_calls == [
            "customer_360_raw:True",
            "customer_360:True",
            "customer_360_raw:True",
            "customer_360:True",
        ]


class TestIcebergNamespacePurgeBehavior:
    """Runtime tests for resilient Iceberg namespace cleanup."""

    @pytest.mark.requirement("AC-1")
    def test_namespace_purge_drops_catalog_metadata_before_s3_sweep(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S3 cleanup must run only after catalog table metadata is removed."""
        dbt_utils = _load_runtime_dbt_utils_module()
        events: list[str] = []

        class _Metadata:
            location = "s3://floe-iceberg/customer_360/orders"

        class _Table:
            metadata = _Metadata()

        class _Catalog:
            dropped = False

            def list_tables(self, namespace: str) -> list[tuple[str, str]]:
                events.append(f"list:{namespace}")
                if self.dropped:
                    return []
                return [("customer_360", "orders")]

            def load_table(self, identifier: str) -> _Table:
                events.append(f"load:{identifier}")
                return _Table()

            def drop_table(self, identifier: str, purge_requested: bool = False) -> None:
                events.append(f"drop:{identifier}:{purge_requested}")
                self.dropped = True

            def purge_table(self, identifier: str) -> None:
                events.append(f"purge:{identifier}")
                raise AssertionError("purge_table must not be used for E2E namespace reset")

            def drop_namespace(self, namespace: str) -> None:
                events.append(f"drop_namespace:{namespace}")

        catalog = _Catalog()
        monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", lambda *, fresh=False: catalog)
        monkeypatch.setattr(dbt_utils, "get_minio_credentials", lambda: ("access", "secret"))
        monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
        monkeypatch.setattr(dbt_utils.boto3, "client", lambda *args, **kwargs: object())

        def _delete_s3_prefix(s3_client: object, bucket: str, prefix: str) -> int:
            del s3_client
            events.append(f"s3_delete:{bucket}:{prefix}")
            return 5

        monkeypatch.setattr(dbt_utils, "_delete_s3_prefix", _delete_s3_prefix)

        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True)

        assert events.index("drop:customer_360.orders:False") < events.index(
            "s3_delete:floe-iceberg:customer_360/orders"
        )
        assert "purge:customer_360.orders" not in events

    @pytest.mark.requirement("AC-1")
    def test_namespace_purge_does_not_delete_s3_when_catalog_drop_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Do not orphan Polaris metadata by deleting files after a failed drop."""
        dbt_utils = _load_runtime_dbt_utils_module()
        events: list[str] = []

        class _Metadata:
            location = "s3://floe-iceberg/customer_360/orders"

        class _Table:
            metadata = _Metadata()

        class _Catalog:
            def list_tables(self, namespace: str) -> list[tuple[str, str]]:
                events.append(f"list:{namespace}")
                return [("customer_360", "orders")]

            def load_table(self, identifier: str) -> _Table:
                events.append(f"load:{identifier}")
                return _Table()

            def drop_table(self, identifier: str, purge_requested: bool = False) -> None:
                events.append(f"drop:{identifier}:{purge_requested}")
                raise RuntimeError("drop forbidden")

            def purge_table(self, identifier: str) -> None:
                events.append(f"purge:{identifier}")
                raise RuntimeError("purge forbidden")

            def drop_namespace(self, namespace: str) -> None:
                events.append(f"drop_namespace:{namespace}")

        catalog = _Catalog()
        monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", lambda *, fresh=False: catalog)
        monkeypatch.setattr(dbt_utils, "get_minio_credentials", lambda: ("access", "secret"))
        monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
        monkeypatch.setattr(dbt_utils.boto3, "client", lambda *args, **kwargs: object())
        monkeypatch.setattr(
            dbt_utils,
            "_delete_s3_prefix",
            lambda *args, **kwargs: events.append("s3_delete"),
        )

        with pytest.raises(dbt_utils.NamespaceResetError, match="Could not drop catalog table"):
            dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)

        assert "drop:customer_360.orders:False" in events
        assert "s3_delete" not in events

    @pytest.mark.requirement("AC-1")
    def test_runtime_teardown_attempts_both_namespaces_before_raising_reset_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Without a prior primary failure, teardown should try both namespaces then raise."""
        import dbt_utils

        runtime_conftest = _load_runtime_conftest_module()
        fixture_func = runtime_conftest.dbt_pipeline_result.__wrapped__

        project_root = tmp_path
        project_dir = project_root / "demo" / "customer-360"
        project_dir.mkdir(parents=True)
        request = SimpleNamespace(param="customer-360")
        purge_calls: list[str] = []

        def _purge(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
            del retries
            purge_calls.append(f"{namespace}:{verify_empty}")
            if len(purge_calls) == 3:
                raise dbt_utils.NamespaceResetError(f"teardown failed for {namespace}")

        def _run_dbt(args: list[str], project_dir_arg: Path) -> SimpleNamespace:
            assert project_dir_arg == project_dir
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _purge)
        monkeypatch.setattr(dbt_utils, "run_dbt", _run_dbt)

        generator = fixture_func(request, project_root, {})

        assert next(generator) == ("customer-360", project_dir)
        with pytest.raises(
            dbt_utils.NamespaceResetError,
            match="teardown failed for customer_360_raw",
        ):
            next(generator)

        assert purge_calls == [
            "customer_360_raw:True",
            "customer_360:True",
            "customer_360_raw:True",
            "customer_360:True",
        ], "Teardown must attempt both namespaces before raising the first reset error."

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize("phase", ["setup", "test_body"])
    def test_runtime_raw_teardown_exception_does_not_mask_primary_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        phase: str,
    ) -> None:
        """Raw teardown exceptions must not replace an earlier dbt or test failure."""
        import dbt_utils

        runtime_conftest = _load_runtime_conftest_module()
        fixture_func = runtime_conftest.dbt_pipeline_result.__wrapped__

        project_root = tmp_path
        project_dir = project_root / "demo" / "customer-360"
        project_dir.mkdir(parents=True)
        request = SimpleNamespace(param="customer-360")
        log_messages: list[str] = []
        purge_calls: list[str] = []

        def _record_error(message: str, *args: object) -> None:
            log_messages.append(message % args if args else message)

        def _purge(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
            del retries
            purge_calls.append(f"{namespace}:{verify_empty}")
            if len(purge_calls) > 2:
                raise RuntimeError(f"raw teardown failure for {namespace}")

        def _run_dbt(args: list[str], project_dir_arg: Path) -> SimpleNamespace:
            assert project_dir_arg == project_dir
            if phase == "setup" and args == ["seed"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="seed exploded")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(runtime_conftest.logger, "error", _record_error)
        monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _purge)
        monkeypatch.setattr(dbt_utils, "run_dbt", _run_dbt)

        generator = fixture_func(request, project_root, {})

        if phase == "setup":
            with pytest.raises(pytest.fail.Exception, match="dbt seed failed"):
                next(generator)
        else:
            assert next(generator) == ("customer-360", project_dir)
            with pytest.raises(RuntimeError, match="test body failed"):
                generator.throw(RuntimeError("test body failed"))

        assert len(log_messages) == 2, (
            "Raw teardown exceptions should be logged for both namespaces when "
            "a primary failure already exists."
        )
        assert all("Suppressed teardown reset failure" in message for message in log_messages), (
            "Suppressed raw teardown failures must be surfaced in logs."
        )
        assert purge_calls == [
            "customer_360_raw:True",
            "customer_360:True",
            "customer_360_raw:True",
            "customer_360:True",
        ]
