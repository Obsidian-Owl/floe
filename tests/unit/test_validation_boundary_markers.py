"""Tests for validation lane markers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_CONFTEST_PATH = REPO_ROOT / "tests" / "e2e" / "conftest.py"
ROOT_CONFTEST_PATH = REPO_ROOT / "tests" / "conftest.py"

pytestmark = pytest.mark.requirement("VAL-LANE-MARKERS")


def _load_e2e_conftest() -> ModuleType:
    """Load the E2E conftest module lazily for structural tests."""
    spec = importlib.util.spec_from_file_location(
        "tests.e2e.conftest_for_validation_markers",
        E2E_CONFTEST_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_root_conftest() -> ModuleType:
    """Load the root tests conftest module lazily for structural tests."""
    spec = importlib.util.spec_from_file_location(
        "tests.conftest_for_validation_markers",
        ROOT_CONFTEST_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pyproject_registers_validation_lane_markers() -> None:
    """Pyproject should declare the validation-lane markers."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert '"bootstrap: Marks admin/bootstrap validation"' in pyproject
    assert '"platform_blackbox: Marks in-cluster product validation"' in pyproject
    assert '"developer_workflow: Marks repo-aware host validation"' in pyproject


def test_e2e_conftest_registers_lane_markers() -> None:
    """The E2E conftest should register the same lane markers at runtime."""
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert "bootstrap: mark test as bootstrap/admin validation" in conftest
    assert "platform_blackbox: mark test as deployed in-cluster product validation" in conftest
    assert "developer_workflow: mark test as repo-aware host validation" in conftest


def test_e2e_conftest_defaults_unclassified_items_to_platform_blackbox() -> None:
    """Unclassified E2E tests should default into the platform lane."""
    conftest = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

    assert "platform_blackbox" in conftest
    assert "item.add_marker(pytest.mark.platform_blackbox)" in conftest


class _FakeConfig:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []
        self.option = SimpleNamespace(reruns=0, reruns_delay=0, fail_on_flaky=False, only_rerun=[])
        self.hook = SimpleNamespace(pytest_deselected=self._record_deselected)
        self.deselected_items: list[_FakeItem] = []

    def addinivalue_line(self, section: str, value: str) -> None:
        self.lines.append((section, value))

    def _record_deselected(self, items: list[_FakeItem]) -> None:
        self.deselected_items.extend(items)


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
    """Runtime pytest configuration should publish the lane markers."""
    config = _FakeConfig()

    _load_e2e_conftest().pytest_configure(config)

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
    """Collection should default lanes and still keep destructive ordering."""
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

    _load_e2e_conftest().pytest_collection_modifyitems(config, items)

    assert items[-1].nodeid == "tests/e2e/test_service_failure_resilience_e2e.py::test_destructive"
    assert items[0].marker_names.count("platform_blackbox") == 1
    assert items[1].marker_names == ["e2e", "bootstrap"]
    assert items[2].marker_names == []
    assert items[3].marker_names.count("platform_blackbox") == 1


def test_pytest_collection_modifyitems_defaults_unmarked_e2e_paths() -> None:
    """Unmarked tests under tests/e2e should still enter the platform lane."""
    config = _FakeConfig()
    items = [
        _FakeItem("tests/e2e/test_asset_discovery.py::test_discovers_assets", []),
        _FakeItem("tests/unit/test_non_e2e.py::test_non_e2e", []),
    ]

    _load_e2e_conftest().pytest_collection_modifyitems(config, items)

    assert items[0].marker_names.count("e2e") == 1
    assert items[0].marker_names.count("platform_blackbox") == 1
    assert items[1].marker_names == []


def test_root_collection_deselects_live_aws_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default test collection should keep live AWS validation opt-in."""
    monkeypatch.delenv("FLOE_RUN_LIVE_AWS_PROVIDER_TESTS", raising=False)
    config = _FakeConfig()
    items = [
        _FakeItem("tests/integration/test_aws_provider_live.py::test_live", ["live_aws"]),
        _FakeItem("tests/integration/test_other.py::test_other", ["integration"]),
    ]

    _load_root_conftest().pytest_collection_modifyitems(config, items)

    assert [item.nodeid for item in items] == ["tests/integration/test_other.py::test_other"]
    assert [item.nodeid for item in config.deselected_items] == [
        "tests/integration/test_aws_provider_live.py::test_live"
    ]


def test_root_collection_keeps_live_aws_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit live AWS lanes should collect tests and enforce their prerequisites."""
    monkeypatch.setenv("FLOE_RUN_LIVE_AWS_PROVIDER_TESTS", "1")
    config = _FakeConfig()
    items = [
        _FakeItem("tests/integration/test_aws_provider_live.py::test_live", ["live_aws"]),
        _FakeItem("tests/integration/test_other.py::test_other", ["integration"]),
    ]

    _load_root_conftest().pytest_collection_modifyitems(config, items)

    assert [item.nodeid for item in items] == [
        "tests/integration/test_aws_provider_live.py::test_live",
        "tests/integration/test_other.py::test_other",
    ]
    assert config.deselected_items == []


def test_selected_items_require_smoke_check_for_platform_blackbox() -> None:
    """Platform-blackbox selections should trigger the smoke check."""
    items = [
        _FakeItem("tests/e2e/test_platform.py::test_live", ["e2e", "platform_blackbox"]),
        _FakeItem("tests/e2e/test_dev.py::test_local", ["developer_workflow"]),
    ]

    assert _load_e2e_conftest()._selected_items_require_infrastructure_smoke_check(items) is True


def test_selected_items_require_smoke_check_for_destructive() -> None:
    """Destructive selections should trigger the smoke check."""
    items = [
        _FakeItem("tests/e2e/test_destructive.py::test_breakage", ["e2e", "destructive"]),
    ]

    assert _load_e2e_conftest()._selected_items_require_infrastructure_smoke_check(items) is True


def test_selected_items_skip_smoke_check_for_developer_workflow_only() -> None:
    """Developer-workflow-only selections should skip the smoke check."""
    items = [
        _FakeItem("tests/e2e/test_profile.py::test_repo", ["e2e", "developer_workflow"]),
        _FakeItem("tests/e2e/test_repo.py::test_governance", ["e2e", "developer_workflow"]),
    ]

    assert _load_e2e_conftest()._selected_items_require_infrastructure_smoke_check(items) is False


def test_selected_items_skip_smoke_check_for_bootstrap_only() -> None:
    """Bootstrap-only selections should skip the smoke check."""
    items = [
        _FakeItem("tests/e2e/test_bootstrap.py::test_admin", ["e2e", "bootstrap"]),
    ]

    assert _load_e2e_conftest()._selected_items_require_infrastructure_smoke_check(items) is False


def test_selected_items_skip_smoke_check_for_bootstrap_and_developer_workflow_only() -> None:
    """Bootstrap plus developer-workflow selections should skip the smoke check."""
    items = [
        _FakeItem("tests/e2e/test_bootstrap.py::test_admin", ["e2e", "bootstrap"]),
        _FakeItem("tests/e2e/test_profile.py::test_repo", ["e2e", "developer_workflow"]),
    ]

    assert _load_e2e_conftest()._selected_items_require_infrastructure_smoke_check(items) is False


def test_bootstrap_modules_are_explicitly_marked() -> None:
    """Bootstrap E2E modules should be explicitly labeled."""
    helm_workflow = (REPO_ROOT / "tests" / "e2e" / "test_helm_workflow.py").read_text()

    assert "pytest.mark.bootstrap" in helm_workflow


def test_platform_runtime_modules_are_explicitly_marked_platform_blackbox() -> None:
    """Runtime-heavy E2E modules should be explicitly labeled as platform blackbox."""
    platform_bootstrap = (REPO_ROOT / "tests" / "e2e" / "test_platform_bootstrap.py").read_text()
    platform_deployment = (
        REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"
    ).read_text()

    assert "pytest.mark.platform_blackbox" in platform_bootstrap
    assert "pytest.mark.platform_blackbox" in platform_deployment


@pytest.mark.requirement("LIVE-VALIDATION")
def test_direct_helm_status_fallback_respects_standard_runner_rbac() -> None:
    """Direct-Helm fallback should only query resources allowed to standard E2E."""
    platform_deployment = (
        REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"
    ).read_text()

    assert '"deployments,services"' in platform_deployment
    assert '"deployments,statefulsets,services"' not in platform_deployment
    assert '"floe-platform-dagster-webserver"' in platform_deployment
    assert '"floe-platform-dagster-daemon"' in platform_deployment


def test_developer_workflow_outliers_are_explicitly_marked() -> None:
    """Repo-aware E2E outliers should be explicitly labeled."""
    profile_isolation = (REPO_ROOT / "tests" / "e2e" / "test_profile_isolation.py").read_text()
    governance = (REPO_ROOT / "tests" / "e2e" / "test_governance.py").read_text()
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert "pytest.mark.developer_workflow" in profile_isolation
    assert "class TestDependencyGovernance" in governance
    assert "@pytest.mark.developer_workflow" in governance
    assert "pytest.mark.developer_workflow" in runtime_loader


def test_runtime_loader_uses_service_contract_not_localhost_literal() -> None:
    """Runtime-loader tests should use the service contract instead of localhost."""
    runtime_loader = (REPO_ROOT / "tests" / "e2e" / "test_runtime_loader_e2e.py").read_text()

    assert 'ServiceEndpoint("dagster-webserver")' in runtime_loader
    assert 'DAGSTER_HOST = "127.0.0.1"' not in runtime_loader
