"""Structural validation: Polaris bootstrap template request bodies and principal role steps.

Tests that ``job-polaris-bootstrap.yaml`` uses correct OpenAPI wrapper format
for all request bodies, creates and assigns principal roles, and counts steps
correctly.

AC-1: Bootstrap job creates and assigns a real principal role
  - Creates principal role via POST /api/management/v1/principal-roles
    with body ``{"principalRole": {"name": "..."}}``
  - Assigns to bootstrap principal via
    PUT /api/management/v1/principals/{name}/principal-roles
    with body ``{"principalRole": {"name": "..."}}``

AC-2: All request bodies use OpenAPI wrapper format
  - Create catalog role: ``{"catalogRole": {"name": "..."}}``
    (currently ``{"name": "..."}``)
  - Grant privilege: ``{"grant": {"type": "catalog", "privilege": "..."}}``
    (currently ``{"type": "catalog", "privilege": "..."}``)
  - Assign catalog role: ``{"catalogRole": {"name": "..."}}``
    (currently ``{"name": "..."}``)

AC-3: Step count adds 5 (not 3) for grants block
  - Currently line 160: ``add $totalSteps 3`` -- should be ``add $totalSteps 5``

AC-6: OAuth scope PRINCIPAL_ROLE:ALL is preserved (not removed)

AC-7: Input validation covers bootstrapPrincipal (new BOOTSTRAP_PRINCIPAL variable)

These are structural (raw text parsing) tests per Constitution V / Pattern P22.
They parse the Helm template as raw text using regex. They do NOT render
templates or deploy anything.

Requirements Covered:
    AC-1: Principal role creation and assignment
    AC-2: OpenAPI wrapper format for request bodies
    AC-3: Step count correctness
    AC-6: OAuth scope preserved
    AC-7: Input validation for bootstrapPrincipal
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FILE = REPO_ROOT / "charts" / "floe-platform" / "templates" / "job-polaris-bootstrap.yaml"


@pytest.fixture(scope="module")
def template_text() -> str:
    """Load the bootstrap template as raw text.

    Returns:
        The complete raw text of job-polaris-bootstrap.yaml.
    """
    assert TEMPLATE_FILE.exists(), (
        f"Bootstrap template not found at {TEMPLATE_FILE}. "
        "Cannot validate template structure without the source file."
    )
    return TEMPLATE_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def grants_block(template_text: str) -> str:
    """Extract the grants-enabled block from the template.

    The grants block starts at ``{{- if .Values.polaris.bootstrap.grants.enabled }}``
    and ends just before ``Bootstrap complete``. This fixture extracts that region
    so tests can assert on grant-specific content without false positives from
    other parts of the template (e.g., the OAuth token request).

    Returns:
        The text content of the grants block.
    """
    match = re.search(
        r"\{\{-?\s*if\s+\.Values\.polaris\.bootstrap\.grants\.enabled\s*\}\}"
        r"(.*?)"
        r"Bootstrap complete",
        template_text,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not locate the grants-enabled block in the bootstrap template. "
        "Expected a block starting with "
        "'{{- if .Values.polaris.bootstrap.grants.enabled }}'"
    )
    return match.group(0)


def _extract_curl_bodies(text: str) -> list[str]:
    """Extract all curl -d body arguments from a block of template text.

    The template uses the pattern: ``-d "{...}")``.
    Inner quotes are escaped as ``\\"``.

    Args:
        text: Raw template text to search.

    Returns:
        List of body strings (including the escaped quotes).
    """
    # Non-greedy .*? is safe here: interior \" are followed by content chars,
    # not [)\s], so the regex only terminates at the true closing quote.
    return re.findall(r'-d\s+"(.*?)"[)\s]', text)


# ---------------------------------------------------------------------------
# AC-3: Step count adds 5 (not 3) for grants block
# ---------------------------------------------------------------------------


class TestStepCount:
    """Verify the grants block adds the correct number of steps.

    The grants block performs 5 operations:
    1. Create catalog role
    2. Grant privileges
    3. Assign catalog role to principal role
    4. Create principal role
    5. Assign principal role to bootstrap principal

    The step count formula must be ``add $totalSteps 5``, not 3.
    """

    @pytest.mark.requirement("AC-3")
    def test_grants_step_count_is_five(self, template_text: str) -> None:
        """The grants block must add exactly 5 to totalSteps, not 3.

        With the addition of principal role creation and assignment steps,
        the grants block performs 5 operations total, not the original 3.
        Using 3 would cause step numbering to be wrong in log output.
        """
        # Find the add $totalSteps within the grants.enabled conditional.
        grants_step_match = re.search(
            r"\{\{-?\s*if\s+\.Values\.polaris\.bootstrap\.grants\.enabled\s*\}\}\s*\n"
            r"\s*\{\{-?\s*\$totalSteps\s*=\s*add\s+\$totalSteps\s+(\d+)\s*\}\}",
            template_text,
        )
        assert grants_step_match is not None, (
            "Could not find 'add $totalSteps N' in the grants.enabled block. "
            "Expected pattern: {{- $totalSteps = add $totalSteps 5 }}"
        )
        step_count = int(grants_step_match.group(1))
        assert step_count == 5, (
            f"Grants block adds {step_count} to totalSteps, expected 5. "
            f"The grants block performs 5 operations: create catalog role, "
            f"grant privileges, assign catalog role to principal role, "
            f"create principal role, assign principal role to bootstrap principal."
        )

    @pytest.mark.requirement("AC-3")
    def test_no_add_totalsteps_three_in_grants(self, template_text: str) -> None:
        """There must be no 'add $totalSteps 3' in the grants block.

        This is a negative test to catch partial fixes where someone changes
        to 5 somewhere but leaves a 3 in another conditional path.
        """
        grants_section = re.search(
            r"(grants\.enabled.*?)Bootstrap complete",
            template_text,
            re.DOTALL,
        )
        assert grants_section is not None, "Could not find grants block"
        grants_text = grants_section.group(0)
        bad_match = re.search(r"\$totalSteps\s*=\s*add\s+\$totalSteps\s+3\b", grants_text)
        assert bad_match is None, (
            "Found 'add $totalSteps 3' in the grants block. "
            "This should be 'add $totalSteps 5' to account for "
            "principal role creation and assignment steps."
        )


# ---------------------------------------------------------------------------
# AC-2: Request body wrappers -- catalog role creation
# ---------------------------------------------------------------------------


class TestCatalogRoleRequestBody:
    """Verify catalog role creation uses OpenAPI wrapper format.

    The Polaris OpenAPI spec requires:
    ``{"catalogRole": {"name": "..."}}``

    NOT the flat format:
    ``{"name": "..."}``
    """

    @pytest.mark.requirement("AC-2")
    def test_create_catalog_role_uses_wrapper(self, grants_block: str) -> None:
        """Create catalog role curl body must use {"catalogRole": {"name": ...}} wrapper.

        The Polaris management API v1 expects catalog role creation requests
        to wrap the role object in a ``catalogRole`` key. Without the wrapper,
        the API may silently ignore the request or return a 400 error.
        """
        # Find the POST to catalog-roles and extract the body from the
        # surrounding curl command. The template pattern is:
        #   curl ... -X POST ... catalog-roles \
        #     -d "{...}")
        post_section = re.search(
            r"-X\s+POST.*?catalog-roles.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert post_section is not None, (
            "Could not find POST to catalog-roles with -d body in grants block."
        )

        body = post_section.group(1)
        has_wrapper = bool(re.search(r"catalogRole", body))
        assert has_wrapper, (
            f"Catalog role creation body is missing 'catalogRole' wrapper key. "
            f"Found body: {body}. "
            f'Expected format: {{"catalogRole": {{"name": "..."}}}}'
        )

    @pytest.mark.requirement("AC-2")
    def test_create_catalog_role_not_flat_name(self, grants_block: str) -> None:
        """Create catalog role must NOT use flat {"name": "..."} format.

        A flat body without the wrapper key is the current broken format.
        This test checks that the POST to catalog-roles does not use a
        body that starts directly with the "name" key.
        """
        post_section = re.search(
            r"-X\s+POST.*?catalog-roles.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert post_section is not None, "Could not find POST to catalog-roles with -d body."

        body = post_section.group(1)
        # A flat body looks like: {\"name\": \"$CATALOG_ROLE\"}
        # It has "name" but no wrapper key like "catalogRole"
        has_name = bool(re.search(r"name", body))
        has_wrapper = bool(re.search(r"catalogRole", body))
        if has_name:
            assert has_wrapper, (
                f"Catalog role creation uses flat body format (has 'name' "
                f"but no 'catalogRole' wrapper): {body}. "
                f'Must use wrapper format: {{"catalogRole": {{"name": "..."}}}}'
            )


# ---------------------------------------------------------------------------
# AC-2: Request body wrappers -- grant privilege
# ---------------------------------------------------------------------------


class TestGrantPrivilegeRequestBody:
    """Verify privilege grant uses OpenAPI wrapper format.

    The Polaris OpenAPI spec requires:
    ``{"grant": {"type": "catalog", "privilege": "..."}}``

    NOT the flat format:
    ``{"type": "catalog", "privilege": "..."}``
    """

    @pytest.mark.requirement("AC-2")
    def test_grant_privilege_uses_wrapper(self, grants_block: str) -> None:
        """Grant privilege curl body must use {"grant": {...}} wrapper.

        The Polaris management API expects grant requests to wrap the grant
        object in a ``grant`` key. Without the wrapper, the API may return
        a 400 or silently fail to apply the grant.
        """
        # Find the -d body near the /grants endpoint
        grant_section = re.search(
            r"/grants.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert grant_section is not None, (
            "Could not find /grants endpoint with -d body in grants block."
        )

        body = grant_section.group(1)
        has_wrapper = bool(re.search(r'\\?"grant\\?"', body))
        assert has_wrapper, (
            f"Grant privilege body is missing 'grant' wrapper key. "
            f"Found body: {body}. "
            f'Expected format: {{"grant": {{"type": "catalog", "privilege": "..."}}}}'
        )

    @pytest.mark.requirement("AC-2")
    def test_grant_privilege_not_flat(self, grants_block: str) -> None:
        """Grant privilege must NOT use flat {"type": ..., "privilege": ...} format.

        The flat format is the current broken state. This test catches
        the case where the body starts directly with "type" without
        a "grant" wrapper.
        """
        grant_section = re.search(
            r"/grants.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert grant_section is not None, "Could not find /grants endpoint with -d body."

        body = grant_section.group(1)
        has_type = bool(re.search(r"type", body))
        has_grant_wrapper = bool(re.search(r'\\?"grant\\?"', body))
        if has_type:
            assert has_grant_wrapper, (
                f"Grant privilege uses flat body format (has 'type' but no "
                f"'grant' wrapper): {body}. "
                f'Must use wrapper: {{"grant": {{"type": "catalog", "privilege": "..."}}}}'
            )


# ---------------------------------------------------------------------------
# AC-2: Request body wrappers -- assign catalog role to principal role
# ---------------------------------------------------------------------------


class TestAssignCatalogRoleRequestBody:
    """Verify catalog role assignment uses OpenAPI wrapper format.

    The Polaris OpenAPI spec requires:
    ``{"catalogRole": {"name": "..."}}``

    NOT the flat format:
    ``{"name": "..."}``
    """

    @pytest.mark.requirement("AC-2")
    def test_assign_catalog_role_uses_wrapper(self, grants_block: str) -> None:
        """Assign catalog role body must use {"catalogRole": {"name": ...}} wrapper.

        The PUT to .../principal-roles/$PRINCIPAL_ROLE/catalog-roles/$CATALOG_NAME
        expects the body to wrap the catalog role reference in a ``catalogRole`` key.
        """
        # The assignment URL contains both principal-roles and catalog-roles segments.
        # Pattern: PUT .../principal-roles/$X/catalog-roles/$Y  -d "..."
        assign_section = re.search(
            r"-X\s+PUT.*?principal-roles/.*?catalog-roles/.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert assign_section is not None, (
            "Could not find PUT to principal-roles/.../catalog-roles/... assignment with -d body."
        )

        body = assign_section.group(1)
        has_wrapper = bool(re.search(r"catalogRole", body))
        assert has_wrapper, (
            f"Catalog role assignment body is missing 'catalogRole' wrapper key. "
            f"Found body: {body}. "
            f'Expected format: {{"catalogRole": {{"name": "..."}}}}'
        )

    @pytest.mark.requirement("AC-2")
    def test_assign_catalog_role_not_flat_name(self, grants_block: str) -> None:
        """Catalog role assignment must NOT use flat {"name": "..."} format.

        The current broken format sends the name directly without the
        catalogRole wrapper. This test catches that specific anti-pattern.
        """
        # Match the specific assignment endpoint (has both principal-roles and catalog-roles)
        assign_section = re.search(
            r"-X\s+PUT.*?principal-roles/.*?catalog-roles/.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        assert assign_section is not None, (
            "Could not find PUT to principal-roles/.../catalog-roles/... assignment with -d body."
        )

        body = assign_section.group(1)
        has_name = bool(re.search(r"name", body))
        has_wrapper = bool(re.search(r"catalogRole", body))
        if has_name:
            assert has_wrapper, (
                f"Catalog role assignment uses flat body format (has 'name' "
                f"but no 'catalogRole' wrapper): {body}. "
                f'Must use wrapper: {{"catalogRole": {{"name": "..."}}}}'
            )


# ---------------------------------------------------------------------------
# AC-1: Principal role creation step
# ---------------------------------------------------------------------------


class TestPrincipalRoleCreation:
    """Verify the template creates a principal role via the management API.

    The bootstrap job must create the principal role before it can assign
    catalog roles to it. This requires a POST to
    ``/api/management/v1/principal-roles`` with body
    ``{"principalRole": {"name": "..."}}``.

    IMPORTANT: The existing URL ``/principal-roles/$PRINCIPAL_ROLE/catalog-roles``
    is NOT a principal role creation endpoint -- it is a catalog role assignment
    endpoint that happens to have ``principal-roles`` in its path. The creation
    endpoint is ``POST /api/management/v1/principal-roles`` (no path parameters).
    """

    @pytest.mark.requirement("AC-1")
    def test_post_to_principal_roles_creation_endpoint(self, grants_block: str) -> None:
        """Template must contain a dedicated POST to create a principal role.

        The creation endpoint is POST /api/management/v1/principal-roles
        (the URL ends at ``principal-roles`` with no further path segments).
        URLs like ``.../principal-roles/$PRINCIPAL_ROLE/catalog-roles`` are
        NOT creation endpoints -- they are catalog role assignment endpoints.

        This test looks for a curl -X POST whose URL ends with
        ``/principal-roles`` followed by a quote or end-of-line, not
        ``/principal-roles/something-else``.
        """
        # Match POST to a URL that ends with /principal-roles (optionally quoted)
        # but NOT /principal-roles/$VAR/something
        has_creation_post = bool(
            re.search(
                r'curl.*-X\s+POST.*?/api/management/v1/principal-roles["\s\')\n]',
                grants_block,
                re.DOTALL,
            )
        )
        if not has_creation_post:
            # Also try the pattern where -X POST comes after the URL
            has_creation_post = bool(
                re.search(
                    r'-X\s+POST[^)]*?principal-roles["\')\s]*\)',
                    grants_block,
                    re.DOTALL,
                )
            )
        assert has_creation_post, (
            "Bootstrap template is missing a POST to /api/management/v1/principal-roles "
            "(the creation endpoint). The existing URL "
            "/principal-roles/$PRINCIPAL_ROLE/catalog-roles is a catalog role "
            "assignment endpoint, NOT a principal role creation endpoint. "
            "Add a curl -X POST to $POLARIS_URL/api/management/v1/principal-roles "
            'with body {"principalRole": {"name": "..."}}'
        )

    @pytest.mark.requirement("AC-1")
    def test_principal_role_creation_body_has_wrapper(self, grants_block: str) -> None:
        """Principal role creation must use {"principalRole": {"name": ...}} wrapper.

        The Polaris management API requires the principal role object to be
        wrapped in a ``principalRole`` key, matching the OpenAPI spec.
        """
        # Extract all curl bodies in the grants block
        all_bodies = _extract_curl_bodies(grants_block)

        # At least one body must contain "principalRole" as a wrapper key
        pr_bodies = [b for b in all_bodies if "principalRole" in b]
        assert len(pr_bodies) > 0, (
            f"No request body in the grants block contains 'principalRole' "
            f"wrapper key. Found {len(all_bodies)} bodies: {all_bodies}. "
            f"Expected at least one body with format: "
            f'{{"principalRole": {{"name": "..."}}}}'
        )

    @pytest.mark.requirement("AC-1")
    def test_principal_role_creation_log_message(self, grants_block: str) -> None:
        """Template must log a step message for principal role creation.

        Each bootstrap step logs its progress. The principal role creation
        step must have a log message mentioning creating a principal role
        (distinct from the existing "catalog role" creation log).
        """
        has_log = bool(
            re.search(
                r'log\s+".*[Cc]reat.*principal\s*role',
                grants_block,
            )
        )
        assert has_log, (
            "Bootstrap template is missing a log message for principal role "
            "creation. Each bootstrap step must log its progress. Expected a "
            "line like: log \"Step .../...: Creating principal role '...'\""
        )


# ---------------------------------------------------------------------------
# AC-1: Principal role assignment to bootstrap principal
# ---------------------------------------------------------------------------


class TestPrincipalRoleAssignment:
    """Verify the template assigns the principal role to the bootstrap principal.

    After creating the principal role, the bootstrap job must assign it to
    the bootstrap principal via PUT to
    ``/api/management/v1/principals/{name}/principal-roles``.
    """

    @pytest.mark.requirement("AC-1")
    def test_put_principals_principal_roles_endpoint_exists(self, grants_block: str) -> None:
        """Template must contain a PUT to /api/management/v1/principals/.../principal-roles.

        This endpoint assigns a principal role to a specific principal
        (the bootstrap principal). Without it, the principal role exists
        but is not assigned to anyone.

        The URL pattern is: /principals/$BOOTSTRAP_PRINCIPAL/principal-roles
        This is distinct from the existing /principal-roles/$PRINCIPAL_ROLE/catalog-roles.
        """
        has_put = bool(
            re.search(
                r"-X\s+PUT.*?/api/management/v1/principals/[^/]+/principal-roles",
                grants_block,
                re.DOTALL,
            )
        )
        assert has_put, (
            "Bootstrap template is missing PUT to "
            "/api/management/v1/principals/{name}/principal-roles. "
            "The bootstrap job must assign the principal role to the "
            "bootstrap principal after creating it. "
            "Note: the existing /principal-roles/$PRINCIPAL_ROLE/catalog-roles "
            "is a different endpoint (catalog role assignment)."
        )

    @pytest.mark.requirement("AC-1")
    def test_principal_role_assignment_body_has_wrapper(self, grants_block: str) -> None:
        """Principal role assignment must use {"principalRole": {"name": ...}} wrapper.

        The PUT endpoint for assigning a principal role expects the body
        to use the standard OpenAPI wrapper format.
        """
        # Find PUT to /principals/.../principal-roles with -d body
        put_match = re.search(
            r"-X\s+PUT.*?/principals/[^/]+/principal-roles.*?-d\s+\"(.*?)\"[)\s]",
            grants_block,
            re.DOTALL,
        )
        if put_match is None:
            pytest.fail(
                "Could not find PUT to /principals/.../principal-roles with -d body. "
                "The endpoint and request body for assigning principal roles "
                "are both missing."
            )

        body = put_match.group(1)
        has_wrapper = bool(re.search(r"principalRole", body))
        assert has_wrapper, (
            f"Principal role assignment body is missing 'principalRole' wrapper. "
            f"Found body: {body}. "
            f'Expected format: {{"principalRole": {{"name": "..."}}}}'
        )

    @pytest.mark.requirement("AC-1")
    def test_assignment_uses_bootstrap_principal_variable(self, grants_block: str) -> None:
        """The PUT URL must reference BOOTSTRAP_PRINCIPAL variable for the principal name.

        The URL pattern should be:
        /api/management/v1/principals/$BOOTSTRAP_PRINCIPAL/principal-roles

        Using a hardcoded principal name instead of the variable would break
        configurability.
        """
        has_var_in_url = bool(
            re.search(
                r"/principals/\$BOOTSTRAP_PRINCIPAL/principal-roles",
                grants_block,
            )
        )
        assert has_var_in_url, (
            "Principal role assignment URL does not use $BOOTSTRAP_PRINCIPAL variable. "
            "Expected: /principals/$BOOTSTRAP_PRINCIPAL/principal-roles. "
            "The bootstrap principal name must come from the BOOTSTRAP_PRINCIPAL "
            "environment variable, not be hardcoded."
        )

    @pytest.mark.requirement("AC-1")
    def test_principal_role_assignment_log_message(self, grants_block: str) -> None:
        """Template must log a step message for assigning principal role to principal.

        This log message is about assigning the principal role TO a principal
        (the bootstrap principal), not about assigning a catalog role to a
        principal role. The log must mention both "principal role" and
        "principal" (the target entity) in the context of assignment.
        """
        # Must mention assigning principal role to a principal (bootstrap principal)
        # The existing log "Assigning catalog role '$CATALOG_ROLE' to principal role"
        # is about a different operation.
        has_log = bool(
            re.search(
                r'log\s+".*[Aa]ssign.*principal\s*role.*\$BOOTSTRAP_PRINCIPAL',
                grants_block,
            )
        )
        assert has_log, (
            "Bootstrap template is missing a log message for assigning the "
            "principal role to the bootstrap principal. Expected a line like: "
            "log \"Step .../...: Assigning principal role '...' to principal "
            "'$BOOTSTRAP_PRINCIPAL'\"  "
            "Note: the existing log about assigning catalog role to principal "
            "role is a different step."
        )


# ---------------------------------------------------------------------------
# AC-7: BOOTSTRAP_PRINCIPAL environment variable and validation
# ---------------------------------------------------------------------------


class TestBootstrapPrincipalVariable:
    """Verify BOOTSTRAP_PRINCIPAL is set from values and validated.

    The template must set a BOOTSTRAP_PRINCIPAL shell variable from
    ``.Values.polaris.bootstrap.grants.bootstrapPrincipal`` and include
    it in the input validation loop.
    """

    @pytest.mark.requirement("AC-7")
    def test_bootstrap_principal_env_var_set(self, grants_block: str) -> None:
        """BOOTSTRAP_PRINCIPAL must be set from .Values.polaris.bootstrap.grants.bootstrapPrincipal.

        Without this variable, the template cannot reference the bootstrap
        principal name in the PUT URL for assigning the principal role.
        """
        has_var = bool(
            re.search(
                r"BOOTSTRAP_PRINCIPAL=.*\.Values\.polaris\.bootstrap\.grants\.bootstrapPrincipal",
                grants_block,
            )
        )
        assert has_var, (
            "Bootstrap template does not set BOOTSTRAP_PRINCIPAL from "
            ".Values.polaris.bootstrap.grants.bootstrapPrincipal. "
            "Expected: BOOTSTRAP_PRINCIPAL="
            '"{{ .Values.polaris.bootstrap.grants.bootstrapPrincipal }}"'
        )

    @pytest.mark.requirement("AC-7")
    def test_bootstrap_principal_in_validation_loop(self, grants_block: str) -> None:
        """BOOTSTRAP_PRINCIPAL must be included in the input validation loop.

        The existing validation loop checks CATALOG_ROLE, CATALOG_NAME,
        and PRINCIPAL_ROLE for shell metacharacters and empty values. The
        new BOOTSTRAP_PRINCIPAL variable must also be validated to prevent
        injection via malicious values.yaml content.
        """
        validation_match = re.search(
            r"for\s+GRANT_VAR_NAME\s+in\s+([\w\s]+);",
            grants_block,
        )
        assert validation_match is not None, (
            "Could not find the input validation loop "
            "(for GRANT_VAR_NAME in ...) in the grants block."
        )

        var_list = validation_match.group(1)
        assert "BOOTSTRAP_PRINCIPAL" in var_list, (
            f"BOOTSTRAP_PRINCIPAL is not in the validation loop. "
            f"Current loop variables: '{var_list.strip()}'. "
            f"BOOTSTRAP_PRINCIPAL must be validated alongside the other "
            f"grant variables to reject shell metacharacters and empty values."
        )


# ---------------------------------------------------------------------------
# AC-6: OAuth scope preservation
# ---------------------------------------------------------------------------


class TestOAuthScopePreserved:
    """Verify the OAuth token request includes PRINCIPAL_ROLE:ALL scope.

    The ``scope=PRINCIPAL_ROLE:ALL`` parameter in the OAuth token request
    is required for the bootstrap job to have permission to manage principal
    roles. This scope must NOT be removed during the template refactoring.
    """

    @pytest.mark.requirement("AC-6")
    def test_principal_role_all_scope_in_oauth_request(self, template_text: str) -> None:
        """OAuth token request must include scope=PRINCIPAL_ROLE:ALL.

        This scope grants the bootstrap job permission to create and manage
        principal roles. Without it, the principal role creation and
        assignment steps would fail with 403 Forbidden.
        """
        has_scope = bool(re.search(r"scope=PRINCIPAL_ROLE:ALL", template_text))
        assert has_scope, (
            "OAuth token request is missing 'scope=PRINCIPAL_ROLE:ALL'. "
            "This scope is required for the bootstrap job to manage "
            "principal roles. It must NOT be removed."
        )

    @pytest.mark.requirement("AC-6")
    def test_scope_is_in_grant_type_request(self, template_text: str) -> None:
        """The PRINCIPAL_ROLE:ALL scope must appear in the same request as grant_type.

        This test verifies the scope is part of the actual OAuth token
        request (containing grant_type=client_credentials), not just
        present somewhere random in the template.
        """
        oauth_match = re.search(
            r"grant_type=client_credentials.*?oauth/tokens",
            template_text,
            re.DOTALL,
        )
        assert oauth_match is not None, (
            "Could not find OAuth token request (grant_type=client_credentials...oauth/tokens)"
        )
        oauth_block = oauth_match.group(0)
        assert "PRINCIPAL_ROLE:ALL" in oauth_block, (
            "OAuth token request block (grant_type...oauth/tokens) does not "
            "contain 'PRINCIPAL_ROLE:ALL'. The scope must be part of the "
            "OAuth token request parameters."
        )


# ---------------------------------------------------------------------------
# AC-2: Comprehensive wrapper format audit (sweep tests)
# ---------------------------------------------------------------------------


class TestNoFlatRequestBodies:
    """Sweep the grants block for any remaining flat (unwrapped) request bodies.

    This is a comprehensive negative test that catches any curl -d body
    in the grants block that uses the old flat format instead of the
    OpenAPI wrapper format.
    """

    @pytest.mark.requirement("AC-2")
    def test_no_flat_name_only_bodies(self, grants_block: str) -> None:
        """No curl -d body in grants block should be just {"name": "..."}.

        The flat format ``{"name": "..."}`` is the old broken format.
        All creation and assignment bodies must use wrapper keys
        (catalogRole, principalRole, grant).
        """
        bodies = _extract_curl_bodies(grants_block)

        flat_bodies: list[str] = []
        for body in bodies:
            has_name = bool(re.search(r"name", body))
            has_wrapper = bool(re.search(r"catalogRole|principalRole|grant", body))
            if has_name and not has_wrapper:
                flat_bodies.append(body)

        assert len(flat_bodies) == 0, (
            f"Found {len(flat_bodies)} flat request body(ies) in grants block "
            f"using the 'name' key without a wrapper key. "
            f"Flat bodies: {flat_bodies}. "
            f"All bodies must use OpenAPI wrapper format: "
            f'{{"catalogRole": ...}}, {{"principalRole": ...}}, or {{"grant": ...}}'
        )

    @pytest.mark.requirement("AC-2")
    def test_no_flat_type_privilege_bodies(self, grants_block: str) -> None:
        """No curl -d body should be just {"type": ..., "privilege": ...}.

        The flat grant format must be wrapped in a ``grant`` key.
        """
        bodies = _extract_curl_bodies(grants_block)

        flat_bodies: list[str] = []
        for body in bodies:
            has_type = bool(re.search(r"type", body))
            has_grant_wrapper = bool(re.search(r'\\?"grant\\?"', body))
            if has_type and not has_grant_wrapper:
                flat_bodies.append(body)

        assert len(flat_bodies) == 0, (
            f"Found {len(flat_bodies)} flat grant body(ies) using "
            f"'type'/'privilege' without the 'grant' wrapper key. "
            f"Flat bodies: {flat_bodies}. "
            f'Expected format: {{"grant": {{"type": "catalog", "privilege": "..."}}}}'
        )


# ---------------------------------------------------------------------------
# AC-1: Step ordering -- principal role creation before catalog role assignment
# ---------------------------------------------------------------------------


class TestStepOrdering:
    """Verify principal role creation happens before catalog role assignment.

    The principal role must exist before a catalog role can be assigned to it.
    The template must create the principal role BEFORE the step that assigns
    the catalog role to the principal role.
    """

    @pytest.mark.requirement("AC-1")
    def test_principal_role_created_before_assigned_catalog_role(self, grants_block: str) -> None:
        """POST /principal-roles (creation) must appear before PUT .../catalog-roles (assignment).

        Creating the principal role is a prerequisite for assigning catalog
        roles to it. If the creation step comes after the assignment, the
        assignment will fail with a 404.
        """
        # Look for POST to principal-roles creation endpoint (URL ends at principal-roles)
        create_match = re.search(
            r'curl.*-X\s+POST.*?/api/management/v1/principal-roles["\s\')\n]',
            grants_block,
            re.DOTALL,
        )
        if create_match is None:
            pytest.fail(
                "Cannot verify step ordering: POST /principal-roles creation "
                "endpoint not found. Principal role creation step is missing."
            )

        # Look for PUT to .../catalog-roles (the assignment step)
        assign_match = re.search(
            r"-X\s+PUT.*?/principal-roles/.*?/catalog-roles",
            grants_block,
            re.DOTALL,
        )
        if assign_match is None:
            pytest.fail(
                "Catalog role assignment (PUT .../catalog-roles) not found. Cannot verify ordering."
            )

        assert create_match.start() < assign_match.start(), (
            "Principal role creation (POST /principal-roles) must appear BEFORE "
            "catalog role assignment (PUT .../catalog-roles) in "
            "the template. The principal role must exist before roles can be "
            "assigned to it."
        )
