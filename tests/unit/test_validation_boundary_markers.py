"""Tests for validation lane markers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_CONFTEST_PATH = REPO_ROOT / "tests" / "e2e" / "conftest.py"

_E2E_CONFTEST_SPEC = importlib.util.spec_from_file_location(
    "tests.e2e.conftest_for_validation_markers",
    E2E_CONFTEST_PATH,
)
assert _E2E_CONFTEST_SPEC is not None
assert _E2E_CONFTEST_SPEC.loader is not None
e2e_conftest = importlib.util.module_from_spec(_E2E_CONFTEST_SPEC)
_E2E_CONFTEST_SPEC.loader.exec_module(e2e_conftest)


def test_pyproject_registers_validation_lane_markers() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert '"bootstrap: Marks admin/bootstrap validation"' in pyproject
    assert '"platform_blackbox: Marks in-cluster product validation"' in pyproject
    assert '"developer_workflow: Marks repo-aware host validation"' in pyproject


def test_e2e_conftest_registers_lane_markers() -> None:
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert 'bootstrap: mark test as bootstrap/admin validation' in conftest
    assert 'platform_blackbox: mark test as deployed in-cluster product validation' in conftest
    assert 'developer_workflow: mark test as repo-aware host validation' in conftest


def test_e2e_conftest_defaults_unclassified_items_to_platform_blackbox() -> None:
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert "platform_blackbox" in conftest
    assert "item.add_marker(pytest.mark.platform_blackbox)" in conftest


class _FakeConfig:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []
        self.option = SimpleNamespace(reruns=0, reruns_delay=0, fail_on_flaky=False, only_rerun=[])

    def addinivalue_line(self, section: str, value: str) -> None:
        self.lines.append((section, value))


class _FakeItem:
    def __init__(self, nodeid: str, marker_names: list[str]) -> None:
        self.nodeid = nodeid
        self._markers = [SimpleNamespace(name=name) for name in marker_names]

    def iter_markers(self) -> list[SimpleNamespace]:
        return list(self._markers)

    def add_marker(self, marker: object) -> None:
        self._markers.append(SimpleNamespace(name=getattr(marker, "name", str(marker))))

    @property
    def marker_names(self) -> list[str]:
        return [marker.name for marker in self._markers]


def test_pytest_configure_registers_validation_lane_markers() -> None:
    config = _FakeConfig()

    e2e_conftest.pytest_configure(config)

    assert (
        "markers",
        "bootstrap: mark test as bootstrap/admin validation",
    ) in config.lines
    assert (
        "markers",
        "platform_blackbox: mark test as deployed in-cluster product validation",
    ) in config.lines
    assert (
        "markers",
        "developer_workflow: mark test as repo-aware host validation",
    ) in config.lines


def test_pytest_collection_modifyitems_defaults_and_preserves_lane_ordering() -> None:
    config = _FakeConfig()
    items = [
        _FakeItem("tests/e2e/test_unclassified.py::test_unclassified", ["e2e"]),
        _FakeItem("tests/e2e/test_bootstrap.py::test_bootstrap", ["e2e", "bootstrap"]),
        _FakeItem(
            "tests/e2e/test_service_failure_resilience_e2e.py::test_destructive",
            ["e2e"],
        ),
        _FakeItem("tests/unit/test_non_e2e.py::test_non_e2e", []),
    ]

    e2e_conftest.pytest_collection_modifyitems(config, items)

    assert items[-1].nodeid == "tests/e2e/test_service_failure_resilience_e2e.py::test_destructive"
    assert items[0].marker_names.count("platform_blackbox") == 1
    assert items[1].marker_names == ["e2e", "bootstrap"]
    assert items[2].marker_names == []
    assert items[3].marker_names.count("platform_blackbox") == 1


def test_selected_items_require_smoke_check_for_platform_blackbox() -> None:
    items = [
        _FakeItem("tests/e2e/test_platform.py::test_live", ["e2e", "platform_blackbox"]),
        _FakeItem("tests/e2e/test_dev.py::test_local", ["developer_workflow"]),
    ]

    assert e2e_conftest._selected_items_require_infrastructure_smoke_check(items) is True


def test_selected_items_require_smoke_check_for_destructive() -> None:
    items = [
        _FakeItem("tests/e2e/test_destructive.py::test_breakage", ["e2e", "destructive"]),
    ]

    assert e2e_conftest._selected_items_require_infrastructure_smoke_check(items) is True


def test_selected_items_skip_smoke_check_for_developer_workflow_only() -> None:
    items = [
        _FakeItem("tests/e2e/test_profile.py::test_repo", ["e2e", "developer_workflow"]),
        _FakeItem("tests/e2e/test_repo.py::test_governance", ["e2e", "developer_workflow"]),
    ]

    assert e2e_conftest._selected_items_require_infrastructure_smoke_check(items) is False


def test_selected_items_skip_smoke_check_for_bootstrap_only() -> None:
    items = [
        _FakeItem("tests/e2e/test_bootstrap.py::test_admin", ["e2e", "bootstrap"]),
    ]

    assert e2e_conftest._selected_items_require_infrastructure_smoke_check(items) is False


def test_selected_items_skip_smoke_check_for_bootstrap_and_developer_workflow_only() -> None:
    items = [
        _FakeItem("tests/e2e/test_bootstrap.py::test_admin", ["e2e", "bootstrap"]),
        _FakeItem("tests/e2e/test_profile.py::test_repo", ["e2e", "developer_workflow"]),
    ]

    assert e2e_conftest._selected_items_require_infrastructure_smoke_check(items) is False


def test_bootstrap_modules_are_explicitly_marked() -> None:
    helm_workflow = (REPO_ROOT / "tests" / "e2e" / "test_helm_workflow.py").read_text()

    assert "pytest.mark.bootstrap" in helm_workflow


def test_platform_runtime_modules_are_explicitly_marked_platform_blackbox() -> None:
    platform_bootstrap = (REPO_ROOT / "tests" / "e2e" / "test_platform_bootstrap.py").read_text()
    platform_deployment = (
        REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"
    ).read_text()

    assert "pytest.mark.platform_blackbox" in platform_bootstrap
    assert "pytest.mark.platform_blackbox" in platform_deployment


def test_developer_workflow_outliers_are_explicitly_marked() -> None:
    profile_isolation = (REPO_ROOT / "tests" / "e2e" / "test_profile_isolation.py").read_text()
    governance = (REPO_ROOT / "tests" / "e2e" / "test_governance.py").read_text()
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert "pytest.mark.developer_workflow" in profile_isolation
    assert "class TestDependencyGovernance" in governance
    assert "@pytest.mark.developer_workflow" in governance
    assert "pytest.mark.developer_workflow" in runtime_loader


def test_runtime_loader_uses_service_contract_not_localhost_literal() -> None:
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert 'ServiceEndpoint("dagster-webserver")' in runtime_loader
    assert 'DAGSTER_HOST = "127.0.0.1"' not in runtime_loader
