"""Structural validation: Polaris RBAC values use real entity names, not scope keywords.

Tests that ``values.yaml`` and ``values-test.yaml`` use real principal role
entity names (like ``floe-pipeline``) rather than Polaris scope keywords
(like ``ALL``) which are misinterpreted by the Polaris RBAC API.

AC-4: Values files use real entity names, not scope keywords
  - ``values.yaml``: ``grants.principalRole`` MUST NOT be ``"ALL"``.
    Default: ``"floe-pipeline"``
  - ``values.yaml``: ``grants.bootstrapPrincipal`` MUST exist.
    Default: ``"root"``
  - ``values-test.yaml``: MUST override ``principalRole`` to a real entity
    name (e.g., ``"floe-pipeline"``)
  - ``values-test.yaml``: MUST set ``bootstrapPrincipal`` explicitly

AC-8: No hardcoded ``"ALL"`` remains as a principal role entity reference

These are structural (YAML-parsing) tests per P22. They load and inspect
the Helm values files. They do NOT render templates or deploy anything.

Requirements Covered:
    AC-4: Values files use real entity names, not scope keywords
    AC-8: No hardcoded "ALL" remains as a principal role entity reference
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VALUES_FILE = REPO_ROOT / "charts" / "floe-platform" / "values.yaml"
VALUES_TEST_FILE = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"

# Polaris scope keywords that are NOT valid entity names.
# These are reserved words in the Polaris RBAC API and must never be used
# as principal role names, catalog role names, or bootstrap principal names.
POLARIS_SCOPE_KEYWORDS = frozenset({"ALL", "all", "All"})

# Pattern for a valid Polaris entity name: alphanumeric, hyphens, underscores.
# Must start with a letter or underscore, length 1-128.
VALID_ENTITY_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]{0,127}$")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file, failing with a clear message if missing."""
    if not path.exists():
        pytest.fail(f"Values file not found: {path}")
    text = path.read_text(encoding="utf-8")
    data: object = yaml.safe_load(text)
    if not isinstance(data, dict):
        pytest.fail(f"Values file did not parse as a dict: {path}")
    return cast(dict[str, Any], data)


def _get_grants(values: dict[str, Any], file_label: str) -> dict[str, Any]:
    """Navigate to polaris.bootstrap.grants, failing if path is missing."""
    polaris: object = values.get("polaris")
    if not isinstance(polaris, dict):
        pytest.fail(f"{file_label}: missing or invalid 'polaris' key")
    polaris_typed = cast(dict[str, Any], polaris)
    bootstrap: object = polaris_typed.get("bootstrap")
    if not isinstance(bootstrap, dict):
        pytest.fail(f"{file_label}: missing or invalid 'polaris.bootstrap' key")
    bootstrap_typed = cast(dict[str, Any], bootstrap)
    grants: object = bootstrap_typed.get("grants")
    if not isinstance(grants, dict):
        pytest.fail(f"{file_label}: missing or invalid 'polaris.bootstrap.grants' key")
    return cast(dict[str, Any], grants)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def values_yaml() -> dict[str, Any]:
    """Load charts/floe-platform/values.yaml."""
    return _load_yaml(VALUES_FILE)


@pytest.fixture(scope="module")
def values_test_yaml() -> dict[str, Any]:
    """Load charts/floe-platform/values-test.yaml."""
    return _load_yaml(VALUES_TEST_FILE)


@pytest.fixture(scope="module")
def values_grants(values_yaml: dict[str, Any]) -> dict[str, Any]:
    """Extract polaris.bootstrap.grants from values.yaml."""
    return _get_grants(values_yaml, "values.yaml")


@pytest.fixture(scope="module")
def values_test_grants(values_test_yaml: dict[str, Any]) -> dict[str, Any]:
    """Extract polaris.bootstrap.grants from values-test.yaml."""
    return _get_grants(values_test_yaml, "values-test.yaml")


# ---------------------------------------------------------------------------
# AC-4: values.yaml principalRole
# ---------------------------------------------------------------------------


class TestValuesYamlPrincipalRole:
    """Tests for principalRole in the default values.yaml."""

    @pytest.mark.requirement("AC-4")
    def test_principal_role_is_not_all(self, values_grants: dict[str, Any]) -> None:
        """principalRole in values.yaml MUST NOT be the scope keyword 'ALL'.

        The Polaris API interprets 'ALL' as a scope keyword, not an entity
        reference. Using it as a principal role name causes silent RBAC
        failures where grants appear to succeed but apply to nothing.
        """
        principal_role = values_grants.get("principalRole")
        assert principal_role not in POLARIS_SCOPE_KEYWORDS, (
            f"values.yaml: grants.principalRole is '{principal_role}' which is a "
            f"Polaris scope keyword, not a real entity name. "
            f"Expected a real principal role like 'floe-pipeline'."
        )

    @pytest.mark.requirement("AC-4")
    def test_principal_role_is_valid_entity_name(self, values_grants: dict[str, Any]) -> None:
        """principalRole must match a valid Polaris entity name pattern.

        Entity names must start with a letter or underscore, contain only
        alphanumeric characters, hyphens, and underscores, and be 1-128
        characters long.
        """
        principal_role = values_grants.get("principalRole")
        assert principal_role is not None, "values.yaml: grants.principalRole is missing"
        assert isinstance(principal_role, str), (
            f"values.yaml: grants.principalRole must be a string, got {type(principal_role)}"
        )
        assert VALID_ENTITY_NAME_PATTERN.match(principal_role), (
            f"values.yaml: grants.principalRole '{principal_role}' does not match "
            f"valid entity name pattern: {VALID_ENTITY_NAME_PATTERN.pattern}"
        )

    @pytest.mark.requirement("AC-4")
    def test_principal_role_has_specific_default(self, values_grants: dict[str, Any]) -> None:
        """principalRole default MUST be 'floe-pipeline', not a generic value.

        This catches implementations that replace 'ALL' with another
        meaningless placeholder like 'default' or 'admin'.
        """
        principal_role = values_grants.get("principalRole")
        assert principal_role == "floe-pipeline", (
            f"values.yaml: grants.principalRole should default to 'floe-pipeline', "
            f"got '{principal_role}'"
        )


# ---------------------------------------------------------------------------
# AC-4: values.yaml bootstrapPrincipal
# ---------------------------------------------------------------------------


class TestValuesYamlBootstrapPrincipal:
    """Tests for bootstrapPrincipal in the default values.yaml."""

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_key_exists(self, values_grants: dict[str, Any]) -> None:
        """grants.bootstrapPrincipal MUST exist in values.yaml.

        The bootstrap job needs to know which Polaris principal to assign
        the principal role to. Without this key, the grant-role API call
        has no target principal.
        """
        assert "bootstrapPrincipal" in values_grants, (
            "values.yaml: grants.bootstrapPrincipal key is missing. "
            "This key is required for the RBAC bootstrap job to assign "
            "the principal role to a Polaris principal."
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_is_not_empty(self, values_grants: dict[str, Any]) -> None:
        """bootstrapPrincipal must have a non-empty string value."""
        bootstrap_principal = values_grants.get("bootstrapPrincipal")
        assert bootstrap_principal is not None, "values.yaml: grants.bootstrapPrincipal is None"
        assert isinstance(bootstrap_principal, str), (
            f"values.yaml: grants.bootstrapPrincipal must be a string, "
            f"got {type(bootstrap_principal)}"
        )
        assert len(bootstrap_principal.strip()) > 0, (
            "values.yaml: grants.bootstrapPrincipal is empty or whitespace"
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_is_valid_entity_name(self, values_grants: dict[str, Any]) -> None:
        """bootstrapPrincipal must match a valid Polaris entity name pattern."""
        bootstrap_principal = values_grants.get("bootstrapPrincipal")
        if bootstrap_principal is None:
            pytest.fail(
                "values.yaml: grants.bootstrapPrincipal is missing "
                "(cannot validate entity name pattern)"
            )
        assert VALID_ENTITY_NAME_PATTERN.match(bootstrap_principal), (
            f"values.yaml: grants.bootstrapPrincipal '{bootstrap_principal}' "
            f"does not match valid entity name pattern"
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_has_specific_default(self, values_grants: dict[str, Any]) -> None:
        """bootstrapPrincipal default MUST be 'root'."""
        bootstrap_principal = values_grants.get("bootstrapPrincipal")
        assert bootstrap_principal == "root", (
            f"values.yaml: grants.bootstrapPrincipal should default to 'root', "
            f"got '{bootstrap_principal}'"
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_is_not_scope_keyword(self, values_grants: dict[str, Any]) -> None:
        """bootstrapPrincipal must not be a Polaris scope keyword."""
        bootstrap_principal = values_grants.get("bootstrapPrincipal")
        assert bootstrap_principal not in POLARIS_SCOPE_KEYWORDS, (
            f"values.yaml: grants.bootstrapPrincipal is '{bootstrap_principal}' "
            f"which is a Polaris scope keyword"
        )


# ---------------------------------------------------------------------------
# AC-4: values-test.yaml principalRole
# ---------------------------------------------------------------------------


class TestValuesTestYamlPrincipalRole:
    """Tests for principalRole in values-test.yaml."""

    @pytest.mark.requirement("AC-4")
    def test_principal_role_is_not_all(self, values_test_grants: dict[str, Any]) -> None:
        """principalRole in values-test.yaml MUST NOT be 'ALL'.

        The test environment must use a real principal role name to
        exercise the actual RBAC grant flow.
        """
        principal_role = values_test_grants.get("principalRole")
        assert principal_role not in POLARIS_SCOPE_KEYWORDS, (
            f"values-test.yaml: grants.principalRole is '{principal_role}' "
            f"which is a Polaris scope keyword, not a real entity name"
        )

    @pytest.mark.requirement("AC-4")
    def test_principal_role_is_valid_entity_name(self, values_test_grants: dict[str, Any]) -> None:
        """principalRole in values-test.yaml must be a valid entity name."""
        principal_role = values_test_grants.get("principalRole")
        assert principal_role is not None, "values-test.yaml: grants.principalRole is missing"
        assert isinstance(principal_role, str), (
            f"values-test.yaml: grants.principalRole must be a string, got {type(principal_role)}"
        )
        assert VALID_ENTITY_NAME_PATTERN.match(principal_role), (
            f"values-test.yaml: grants.principalRole '{principal_role}' "
            f"does not match valid entity name pattern"
        )


# ---------------------------------------------------------------------------
# AC-4: values-test.yaml bootstrapPrincipal
# ---------------------------------------------------------------------------


class TestValuesTestYamlBootstrapPrincipal:
    """Tests for bootstrapPrincipal in values-test.yaml."""

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_key_exists(self, values_test_grants: dict[str, Any]) -> None:
        """grants.bootstrapPrincipal MUST be set explicitly in values-test.yaml.

        Test environments must explicitly configure which principal receives
        the role, not rely on defaults.
        """
        assert "bootstrapPrincipal" in values_test_grants, (
            "values-test.yaml: grants.bootstrapPrincipal key is missing. "
            "Test environment must explicitly set the bootstrap principal."
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_is_valid_entity_name(
        self, values_test_grants: dict[str, Any]
    ) -> None:
        """bootstrapPrincipal in values-test.yaml must be a valid entity name."""
        bootstrap_principal = values_test_grants.get("bootstrapPrincipal")
        if bootstrap_principal is None:
            pytest.fail(
                "values-test.yaml: grants.bootstrapPrincipal is missing "
                "(cannot validate entity name pattern)"
            )
        assert isinstance(bootstrap_principal, str), (
            f"values-test.yaml: grants.bootstrapPrincipal must be a string, "
            f"got {type(bootstrap_principal)}"
        )
        assert VALID_ENTITY_NAME_PATTERN.match(bootstrap_principal), (
            f"values-test.yaml: grants.bootstrapPrincipal '{bootstrap_principal}' "
            f"does not match valid entity name pattern"
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_principal_is_not_scope_keyword(
        self, values_test_grants: dict[str, Any]
    ) -> None:
        """bootstrapPrincipal in values-test.yaml must not be a scope keyword."""
        bootstrap_principal = values_test_grants.get("bootstrapPrincipal")
        assert bootstrap_principal not in POLARIS_SCOPE_KEYWORDS, (
            f"values-test.yaml: grants.bootstrapPrincipal is '{bootstrap_principal}' "
            f"which is a Polaris scope keyword"
        )


# ---------------------------------------------------------------------------
# AC-8: No "ALL" as principal role anywhere
# ---------------------------------------------------------------------------


class TestNoScopeKeywordsAsEntityNames:
    """Sweep both values files for any use of scope keywords as entity names."""

    @pytest.mark.requirement("AC-8")
    def test_values_yaml_no_all_as_principal_role(self, values_yaml: dict[str, Any]) -> None:
        """No principalRole in values.yaml may be set to 'ALL'.

        This is a deep scan: it walks the entire YAML tree looking for
        any key named 'principalRole' whose value is a scope keyword.
        This catches nested or future grant blocks beyond polaris.bootstrap.
        """
        violations = _find_scope_keyword_violations(values_yaml, "principalRole")
        assert not violations, (
            f"values.yaml: Found 'ALL' or other scope keywords used as "
            f"principalRole values at: {violations}"
        )

    @pytest.mark.requirement("AC-8")
    def test_values_test_yaml_no_all_as_principal_role(
        self, values_test_yaml: dict[str, Any]
    ) -> None:
        """No principalRole in values-test.yaml may be set to 'ALL'.

        Deep scan of entire values-test.yaml tree.
        """
        violations = _find_scope_keyword_violations(values_test_yaml, "principalRole")
        assert not violations, (
            f"values-test.yaml: Found 'ALL' or other scope keywords used as "
            f"principalRole values at: {violations}"
        )

    @pytest.mark.requirement("AC-8")
    def test_values_yaml_no_all_as_bootstrap_principal(self, values_yaml: dict[str, Any]) -> None:
        """No bootstrapPrincipal in values.yaml may be set to 'ALL'."""
        violations = _find_scope_keyword_violations(values_yaml, "bootstrapPrincipal")
        assert not violations, (
            f"values.yaml: Found scope keywords used as bootstrapPrincipal values at: {violations}"
        )

    @pytest.mark.requirement("AC-8")
    def test_values_test_yaml_no_all_as_bootstrap_principal(
        self, values_test_yaml: dict[str, Any]
    ) -> None:
        """No bootstrapPrincipal in values-test.yaml may be set to 'ALL'."""
        violations = _find_scope_keyword_violations(values_test_yaml, "bootstrapPrincipal")
        assert not violations, (
            f"values-test.yaml: Found scope keywords used as "
            f"bootstrapPrincipal values at: {violations}"
        )

    @pytest.mark.requirement("AC-8")
    def test_raw_yaml_no_principal_role_all_pattern(self) -> None:
        """Raw text scan: no line matches 'principalRole: "ALL"' in either file.

        This catches cases where YAML structure tricks (anchors, aliases)
        might hide a value from the parsed dict walk.
        """
        pattern = re.compile(r"""principalRole:\s*["']?ALL["']?""", re.IGNORECASE)
        for path in (VALUES_FILE, VALUES_TEST_FILE):
            text = path.read_text(encoding="utf-8")
            matches = pattern.findall(text)
            assert not matches, (
                f"{path.name}: Found raw text match for principalRole=ALL: {matches}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_scope_keyword_violations(data: Any, target_key: str, path: str = "") -> list[str]:
    """Recursively find any key named ``target_key`` whose value is a scope keyword.

    Returns a list of dotted paths where violations occur.
    """
    violations: list[str] = []
    if isinstance(data, dict):
        typed_data = cast(dict[str, Any], data)
        for key_str, value_any in typed_data.items():
            current_path: str = f"{path}.{key_str}" if path else str(key_str)
            if (
                str(key_str) == target_key
                and isinstance(value_any, str)
                and value_any in POLARIS_SCOPE_KEYWORDS
            ):
                violations.append(f"{current_path}={value_any}")
            violations.extend(_find_scope_keyword_violations(value_any, target_key, current_path))
    elif isinstance(data, list):
        typed_list = cast(list[Any], data)
        for i, item in enumerate(typed_list):
            violations.extend(_find_scope_keyword_violations(item, target_key, f"{path}[{i}]"))
    return violations
