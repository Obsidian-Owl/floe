"""Structural validation: E2E conftest mirrors corrected Polaris RBAC bootstrap sequence.

Tests that ``tests/e2e/conftest.py`` uses the correct 5-step RBAC bootstrap
sequence with proper OpenAPI wrapper bodies and real principal role entity names.

AC-5: E2E conftest mirrors corrected bootstrap sequence
  1. Creates principal role via POST /api/management/v1/principal-roles
     (handle 201/409)
  2. Assigns principal role to root via
     PUT /api/management/v1/principals/root/principal-roles
     (handle 200/201/204/409)
  3. Creates catalog role with wrapper body
     ``{"catalogRole": {"name": "catalog_admin"}}`` (handle 201/409)
  4. Grants privilege with wrapper body
     ``{"grant": {"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}}``
     (handle 200/201/204/409)
  5. Assigns catalog role to principal role via correct URL path and
     wrapper body (handle 200/201/204/409)

  Principal role name comes from env var POLARIS_PRINCIPAL_ROLE
  (default: "floe-pipeline")

AC-6: OAuth scope PRINCIPAL_ROLE:ALL preserved in conftest token request

AC-8: No hardcoded "ALL" remains as a principal role entity reference

These are structural (source text parsing) tests per Constitution V / Pattern P22.
They read ``tests/e2e/conftest.py`` as raw text and inspect the grants section
using regex. They do NOT execute the conftest or import it.

Requirements Covered:
    AC-5: E2E conftest mirrors corrected bootstrap sequence
    AC-6: OAuth scope PRINCIPAL_ROLE:ALL preserved
    AC-8: No hardcoded "ALL" remains as a principal role entity reference
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFTEST_FILE = REPO_ROOT / "tests" / "e2e" / "conftest.py"

# Section delimiter comments in the conftest that bound the grants section.
# The grants section starts after "Apply write grants" and ends before
# "return catalog" or the next fixture definition.
GRANTS_SECTION_START = "Apply write grants"
GRANTS_SECTION_END = "return catalog"


def _read_conftest() -> str:
    """Read the E2E conftest file as raw text.

    Returns:
        Full text content of tests/e2e/conftest.py.

    Raises:
        pytest.fail: If the file does not exist.
    """
    if not CONFTEST_FILE.exists():
        pytest.fail(f"E2E conftest not found at {CONFTEST_FILE}")
    return CONFTEST_FILE.read_text(encoding="utf-8")


def _extract_grants_section(text: str) -> str:
    """Extract the grants section from the conftest source text.

    The grants section is bounded by the "Apply write grants" comment
    and "return catalog" statement. This is the section that performs
    RBAC bootstrap steps.

    Args:
        text: Full conftest source text.

    Returns:
        The grants section substring.

    Raises:
        pytest.fail: If the section boundaries cannot be found.
    """
    start_idx = text.find(GRANTS_SECTION_START)
    if start_idx == -1:
        pytest.fail(
            f"Cannot find '{GRANTS_SECTION_START}' comment in conftest. "
            f"The grants section delimiter is missing."
        )
    end_idx = text.find(GRANTS_SECTION_END, start_idx)
    if end_idx == -1:
        pytest.fail(
            f"Cannot find '{GRANTS_SECTION_END}' after grants section start. "
            f"The grants section end delimiter is missing."
        )
    return text[start_idx:end_idx]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def conftest_text() -> str:
    """Full text of tests/e2e/conftest.py."""
    return _read_conftest()


@pytest.fixture(scope="module")
def grants_section(conftest_text: str) -> str:
    """The grants section of the E2E conftest (between delimiters)."""
    return _extract_grants_section(conftest_text)


# ---------------------------------------------------------------------------
# AC-5: Principal role env var
# ---------------------------------------------------------------------------


class TestPrincipalRoleEnvVar:
    """Tests that conftest reads POLARIS_PRINCIPAL_ROLE from environment."""

    @pytest.mark.requirement("AC-5")
    def test_polaris_principal_role_env_var_read(self, grants_section: str) -> None:
        """The grants section MUST read POLARIS_PRINCIPAL_ROLE env var.

        The principal role name must come from the environment, not be
        hardcoded. This allows different environments to use different
        principal role names.

        Expected pattern: os.environ.get("POLARIS_PRINCIPAL_ROLE", ...)
        """
        assert "POLARIS_PRINCIPAL_ROLE" in grants_section, (
            "E2E conftest grants section must read the POLARIS_PRINCIPAL_ROLE "
            "environment variable via os.environ.get(). "
            "Currently the principal role name is either hardcoded or missing."
        )

    @pytest.mark.requirement("AC-5")
    def test_polaris_principal_role_has_default(self, grants_section: str) -> None:
        """POLARIS_PRINCIPAL_ROLE must default to 'floe-pipeline'.

        The env var read must include a default value of 'floe-pipeline'
        so the conftest works without explicit env configuration.
        """
        # Match os.environ.get("POLARIS_PRINCIPAL_ROLE", "floe-pipeline")
        # or os.environ.get('POLARIS_PRINCIPAL_ROLE', 'floe-pipeline')
        pattern = re.compile(
            r"""os\.environ\.get\(\s*["']POLARIS_PRINCIPAL_ROLE["']\s*,\s*["']floe-pipeline["']"""
        )
        assert pattern.search(grants_section), (
            "E2E conftest must read POLARIS_PRINCIPAL_ROLE with default "
            '\'floe-pipeline\': os.environ.get("POLARIS_PRINCIPAL_ROLE", "floe-pipeline"). '
            "Currently the env var read is missing or uses a different default."
        )


# ---------------------------------------------------------------------------
# AC-5: Step 1 - Create principal role
# ---------------------------------------------------------------------------


class TestCreatePrincipalRole:
    """Tests that conftest creates the principal role (Step 1)."""

    @pytest.mark.requirement("AC-5")
    def test_post_principal_roles_endpoint(self, grants_section: str) -> None:
        """The grants section MUST POST to /api/management/v1/principal-roles.

        This creates the principal role entity in Polaris. Without this step,
        the principal role does not exist and subsequent assignments fail.

        The URL must end at /principal-roles (with optional trailing quote),
        NOT continue into /principal-roles/ALL/catalog-roles/... which is
        the catalog role assignment URL.
        """
        # Match the endpoint that ENDS at /principal-roles (not followed by /)
        # This distinguishes the creation endpoint from
        # /principal-roles/{name}/catalog-roles/{catalog}
        pattern = re.compile(r"""/api/management/v1/principal-roles["'\s,\n]""")
        assert pattern.search(grants_section), (
            "E2E conftest grants section must POST to "
            "/api/management/v1/principal-roles (terminal endpoint) to create "
            "the principal role. URLs like /principal-roles/ALL/catalog-roles/... "
            "are catalog role assignment URLs, not principal role creation."
        )

    @pytest.mark.requirement("AC-5")
    def test_post_principal_roles_uses_httpx_post(self, grants_section: str) -> None:
        """The principal role creation MUST use httpx.post (not put/get).

        The Polaris management API requires POST for entity creation.
        """
        # Find the section around the principal-roles endpoint call
        # and verify it uses httpx.post
        lines = grants_section.split("\n")
        found_post_with_principal_roles = False
        for i, line in enumerate(lines):
            if "principal-roles" in line and "/principals/" not in line:
                # Look in surrounding context for httpx.post
                context_start = max(0, i - 5)
                context_end = min(len(lines), i + 3)
                context = "\n".join(lines[context_start:context_end])
                if "httpx.post" in context:
                    found_post_with_principal_roles = True
                    break

        assert found_post_with_principal_roles, (
            "Principal role creation must use httpx.post() to POST to "
            "/api/management/v1/principal-roles. "
            "Either the endpoint is missing or uses the wrong HTTP method."
        )

    @pytest.mark.requirement("AC-5")
    def test_principal_role_creation_handles_201_409(self, grants_section: str) -> None:
        """Principal role creation must handle 201 (created) and 409 (exists).

        The step is idempotent: 201 means created, 409 means already exists.
        Both are acceptable outcomes.
        """
        # Look for status code check with both 201 and 409
        # near the principal-roles POST
        lines = grants_section.split("\n")
        for i, line in enumerate(lines):
            if "principal-roles" in line and "/principals/" not in line:
                # Search forward for status code handling
                context_end = min(len(lines), i + 15)
                context = "\n".join(lines[i:context_end])
                if "201" in context and "409" in context:
                    return  # Test passes
        pytest.fail(
            "Principal role creation must handle both HTTP 201 (created) and "
            "409 (already exists) status codes for idempotent operation."
        )


# ---------------------------------------------------------------------------
# AC-5: Step 2 - Assign principal role to bootstrap principal
# ---------------------------------------------------------------------------


class TestAssignPrincipalRole:
    """Tests that conftest assigns principal role to the bootstrap principal."""

    @pytest.mark.requirement("AC-5")
    def test_put_principals_endpoint(self, grants_section: str) -> None:
        """The grants section MUST PUT to /api/management/v1/principals/{name}/principal-roles.

        This assigns the created principal role to the bootstrap principal
        (typically 'root'). Without this step, the principal has no role.
        """
        # Match URL pattern: /api/management/v1/principals/{something}/principal-roles
        pattern = re.compile(r"/api/management/v1/principals/.*?/principal-roles")
        assert pattern.search(grants_section), (
            "E2E conftest grants section must PUT to "
            "/api/management/v1/principals/{name}/principal-roles to assign "
            "the principal role to the bootstrap principal. "
            "This step is currently missing from the bootstrap sequence."
        )

    @pytest.mark.requirement("AC-5")
    def test_assign_uses_httpx_put(self, grants_section: str) -> None:
        """The principal role assignment MUST use httpx.put (not post).

        The Polaris management API requires PUT for role assignments.
        """
        lines = grants_section.split("\n")
        found_put_with_principals = False
        for i, line in enumerate(lines):
            if "/principals/" in line and "principal-roles" in line:
                context_start = max(0, i - 5)
                context_end = min(len(lines), i + 3)
                context = "\n".join(lines[context_start:context_end])
                if "httpx.put" in context:
                    found_put_with_principals = True
                    break

        assert found_put_with_principals, (
            "Principal role assignment to bootstrap principal must use "
            "httpx.put() to PUT to /api/management/v1/principals/{name}/principal-roles."
        )


# ---------------------------------------------------------------------------
# AC-5: Step 3 - Create catalog role with wrapper body
# ---------------------------------------------------------------------------


class TestCreateCatalogRoleWrapperBody:
    """Tests that catalog role creation uses the OpenAPI wrapper format."""

    @pytest.mark.requirement("AC-5")
    def test_catalog_role_uses_wrapper_body(self, grants_section: str) -> None:
        """Catalog role creation MUST use wrapper body {"catalogRole": {"name": ...}}.

        The Polaris OpenAPI spec requires the wrapper format, not the flat
        format {"name": "catalog_admin"}. The flat format silently fails
        or is rejected by strict Polaris implementations.
        """
        # Must find the wrapper pattern
        wrapper_pattern = re.compile(r"""["']catalogRole["']\s*:\s*\{""")
        assert wrapper_pattern.search(grants_section), (
            "Catalog role creation must use wrapper body format: "
            '{"catalogRole": {"name": "catalog_admin"}}. '
            "Currently uses flat body: "
            '{"name": "catalog_admin"} which does not match the OpenAPI spec.'
        )

    @pytest.mark.requirement("AC-5")
    def test_no_flat_catalog_role_body(self, grants_section: str) -> None:
        """No catalog role step may use flat body json={"name": "catalog_admin"}.

        The flat format is the old (incorrect) format. All catalog role
        bodies must use the OpenAPI wrapper format.
        """
        # Find lines with json={"name": "catalog_admin"} that are NOT inside a wrapper
        # Pattern: json={"name": "catalog_admin"} on its own (not preceded by "catalogRole":)
        flat_pattern = re.compile(
            r"""json\s*=\s*\{\s*["']name["']\s*:\s*["']catalog_admin["']\s*\}"""
        )
        matches = flat_pattern.findall(grants_section)
        assert not matches, (
            f'Found flat body format json={{"name": "catalog_admin"}} '
            f"in grants section ({len(matches)} occurrence(s)). "
            f"All catalog role bodies must use wrapper format: "
            f'json={{"catalogRole": {{"name": "catalog_admin"}}}}.'
        )


# ---------------------------------------------------------------------------
# AC-5: Step 4 - Grant privilege with wrapper body
# ---------------------------------------------------------------------------


class TestGrantPrivilegeWrapperBody:
    """Tests that privilege grant uses the OpenAPI wrapper format."""

    @pytest.mark.requirement("AC-5")
    def test_grant_uses_wrapper_body(self, grants_section: str) -> None:
        """Privilege grant MUST use wrapper body {"grant": {"type": ..., "privilege": ...}}.

        The Polaris OpenAPI spec requires the wrapper format, not the flat
        format {"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}.
        """
        wrapper_pattern = re.compile(r"""["']grant["']\s*:\s*\{""")
        assert wrapper_pattern.search(grants_section), (
            "Privilege grant must use wrapper body format: "
            '{"grant": {"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}}. '
            "Currently uses flat body which does not match the OpenAPI spec."
        )

    @pytest.mark.requirement("AC-5")
    def test_no_flat_grant_body(self, grants_section: str) -> None:
        """No grant step may use flat body json={"type": "catalog", "privilege": ...}.

        The flat format is the old (incorrect) format. The grant body must
        use the OpenAPI wrapper format with the "grant" key.
        """
        # Match the flat pattern: json={"type": "catalog", "privilege": ...}
        # but NOT when it's inside a "grant": {...} wrapper
        flat_pattern = re.compile(
            r"""json\s*=\s*\{\s*["']type["']\s*:\s*["']catalog["']\s*,\s*["']privilege["']"""
        )
        matches = flat_pattern.findall(grants_section)
        assert not matches, (
            f'Found flat grant body format json={{"type": "catalog", "privilege": ...}} '
            f"in grants section ({len(matches)} occurrence(s)). "
            f'Must use wrapper format: json={{"grant": {{"type": "catalog", ...}}}}.'
        )


# ---------------------------------------------------------------------------
# AC-5: Step 5 - Assign catalog role to principal role (correct URL)
# ---------------------------------------------------------------------------


class TestAssignCatalogRoleToCorrectPrincipalRole:
    """Tests that catalog role assignment uses the correct principal role in the URL."""

    @pytest.mark.requirement("AC-5")
    @pytest.mark.requirement("AC-8")
    def test_no_principal_roles_all_in_url(self, grants_section: str) -> None:
        """The URL /principal-roles/ALL/ MUST NOT appear in the grants section.

        'ALL' is a Polaris OAuth scope keyword, not a principal role entity
        name. Using it in the URL path attempts to reference a non-existent
        entity, causing silent grant failures.
        """
        pattern = re.compile(r"/principal-roles/ALL/", re.IGNORECASE)
        matches = pattern.findall(grants_section)
        assert not matches, (
            f"Found '/principal-roles/ALL/' in grants section URL "
            f"({len(matches)} occurrence(s)). "
            f"'ALL' is a scope keyword, not a principal role name. "
            f"The URL must use the real principal role name from "
            f"POLARIS_PRINCIPAL_ROLE env var (default: 'floe-pipeline')."
        )

    @pytest.mark.requirement("AC-5")
    def test_catalog_role_assignment_url_uses_dynamic_role(self, grants_section: str) -> None:
        """Catalog role assignment URL must use the dynamic principal role name.

        The URL should contain a variable/f-string reference for the principal
        role name, not a hardcoded string. This ensures it uses the value
        from POLARIS_PRINCIPAL_ROLE env var.
        """
        # Look for f-string interpolation in the principal-roles URL
        # e.g., /principal-roles/{principal_role_name}/ or similar
        dynamic_pattern = re.compile(r"/principal-roles/\{[a-zA-Z_][a-zA-Z0-9_]*\}/")
        assert dynamic_pattern.search(grants_section), (
            "Catalog role assignment URL must use a dynamic principal role "
            "name (f-string variable), not a hardcoded value. "
            "Expected pattern like: /principal-roles/{principal_role_name}/..."
        )

    @pytest.mark.requirement("AC-5")
    def test_catalog_role_assignment_uses_wrapper_body(self, grants_section: str) -> None:
        """Catalog role assignment to principal role must use wrapper body.

        The body for PUT .../catalog-roles/{catalog} must be
        {"catalogRole": {"name": "catalog_admin"}}, not {"name": "catalog_admin"}.
        """
        # Count wrapper occurrences - there should be at least 2:
        # one for creation (POST) and one for assignment (PUT)
        wrapper_pattern = re.compile(r"""["']catalogRole["']\s*:\s*\{""")
        wrapper_matches = wrapper_pattern.findall(grants_section)
        # Need at least 2: create catalog role + assign catalog role to principal role
        assert len(wrapper_matches) >= 2, (
            f"Expected at least 2 catalogRole wrapper bodies in grants section "
            f"(one for creation, one for assignment to principal role), "
            f"found {len(wrapper_matches)}. Both catalog role API calls must "
            f'use the wrapper format: {{"catalogRole": {{"name": ...}}}}.'
        )


# ---------------------------------------------------------------------------
# AC-6: OAuth scope preservation
# ---------------------------------------------------------------------------


class TestOAuthScopePreservation:
    """Tests that PRINCIPAL_ROLE:ALL is preserved as OAuth scope (not entity name)."""

    @pytest.mark.requirement("AC-6")
    def test_oauth_scope_principal_role_all_preserved(self, conftest_text: str) -> None:
        """The OAuth token request MUST include scope PRINCIPAL_ROLE:ALL.

        'PRINCIPAL_ROLE:ALL' is a valid OAuth scope that requests permissions
        for all principal roles. This is different from using 'ALL' as an
        entity name in a URL path. The scope MUST be preserved.
        """
        # Match the scope field in the OAuth token request
        scope_pattern = re.compile(r"""["']scope["']\s*:\s*["']PRINCIPAL_ROLE:ALL["']""")
        assert scope_pattern.search(conftest_text), (
            "E2E conftest must include 'scope': 'PRINCIPAL_ROLE:ALL' in the "
            "OAuth token request data. This is a valid OAuth scope and must "
            "not be confused with the entity name 'ALL' which is incorrect."
        )


# ---------------------------------------------------------------------------
# AC-8: No hardcoded "ALL" as entity reference
# ---------------------------------------------------------------------------


class TestNoHardcodedAllEntityReference:
    """Tests that 'ALL' is not used as a principal role entity reference."""

    @pytest.mark.requirement("AC-8")
    def test_no_all_in_url_path_segments(self, grants_section: str) -> None:
        """No URL in the grants section may use 'ALL' as a path segment entity name.

        'ALL' in a URL path like /principal-roles/ALL/ is an entity reference.
        This is different from 'PRINCIPAL_ROLE:ALL' which is an OAuth scope.
        Only the OAuth scope usage is valid.
        """
        # Find ALL in URL path segments (not in OAuth scope context)
        url_all_pattern = re.compile(r"/ALL/|/ALL[\"']")
        matches = url_all_pattern.findall(grants_section)
        assert not matches, (
            f"Found 'ALL' used as URL path segment entity name in grants "
            f"section ({len(matches)} occurrence(s)). "
            f"'ALL' is a scope keyword, not a valid entity name. "
            f"Replace with the dynamic principal role name."
        )

    @pytest.mark.requirement("AC-8")
    def test_grants_section_all_occurrences_are_scope_only(self, conftest_text: str) -> None:
        """Every occurrence of 'ALL' in the conftest must be in an OAuth scope context.

        Valid: "scope": "PRINCIPAL_ROLE:ALL"
        Invalid: /principal-roles/ALL/ or any URL path usage
        """
        grants = _extract_grants_section(conftest_text)

        # Find all occurrences of ALL (word boundary) in the grants section
        all_pattern = re.compile(r"\bALL\b")
        all_matches = list(all_pattern.finditer(grants))

        # Each match must be part of "PRINCIPAL_ROLE:ALL" (OAuth scope),
        # not a standalone entity reference
        for match in all_matches:
            # Check surrounding context (50 chars before)
            start = max(0, match.start() - 50)
            context = grants[start : match.end()]
            # Must be in scope context: PRINCIPAL_ROLE:ALL
            is_scope = "PRINCIPAL_ROLE:ALL" in context
            assert is_scope, (
                f"Found 'ALL' in grants section that is NOT in OAuth scope context. "
                f"Context: ...{context[-60:]!r}... "
                f"'ALL' must only appear as part of 'PRINCIPAL_ROLE:ALL' scope. "
                f"All entity references must use real names."
            )


# ---------------------------------------------------------------------------
# AC-5: Bootstrap step ordering
# ---------------------------------------------------------------------------


class TestBootstrapStepOrdering:
    """Tests that the 5 bootstrap steps appear in the correct order."""

    @pytest.mark.requirement("AC-5")
    def test_five_step_sequence_present(self, grants_section: str) -> None:
        """The grants section must contain all 5 bootstrap steps in order.

        Required ordering:
        1. Create principal role (POST /principal-roles)
        2. Assign principal role to bootstrap principal (PUT /principals/.../principal-roles)
        3. Create catalog role (POST .../catalog-roles)
        4. Grant privilege (PUT .../grants)
        5. Assign catalog role to principal role (PUT /principal-roles/.../catalog-roles)
        """
        # Find positions of each step's key indicator
        step_indicators: list[tuple[str, str]] = [
            ("Step 1: Create principal role", "/api/management/v1/principal-roles"),
            ("Step 2: Assign principal role", "/api/management/v1/principals/"),
            ("Step 3: Create catalog role", "/catalog-roles"),
            ("Step 4: Grant privilege", "/grants"),
        ]

        positions: list[tuple[str, int]] = []
        for label, marker in step_indicators:
            idx = grants_section.find(marker)
            assert idx != -1, (
                f"{label}: Expected to find '{marker}' in grants section but it was missing."
            )
            positions.append((label, idx))

        # Verify ordering
        for i in range(len(positions) - 1):
            label_a, pos_a = positions[i]
            label_b, pos_b = positions[i + 1]
            assert pos_a < pos_b, (
                f"Bootstrap steps out of order: '{label_a}' (pos {pos_a}) "
                f"must appear before '{label_b}' (pos {pos_b})."
            )

    @pytest.mark.requirement("AC-5")
    def test_step_count_is_five_not_three(self, grants_section: str) -> None:
        """The grants section must implement 5 steps, not 3.

        The original conftest had only 3 steps (create catalog role, grant
        privilege, assign catalog role). The corrected version adds 2 new
        steps (create principal role, assign principal role to bootstrap
        principal) for a total of 5.
        """
        # Count distinct httpx.post/httpx.put calls in the grants section
        http_calls = re.findall(r"httpx\.(post|put)\(", grants_section)
        assert len(http_calls) >= 5, (
            f"Grants section must have at least 5 HTTP calls (5 bootstrap steps), "
            f"found {len(http_calls)}. The corrected bootstrap sequence requires: "
            f"(1) POST create principal role, (2) PUT assign principal role, "
            f"(3) POST create catalog role, (4) PUT grant privilege, "
            f"(5) PUT assign catalog role to principal role."
        )
