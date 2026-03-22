"""Unit tests for dynamic asset discovery in E2E materialization.

Tests the _discover_repository_for_asset() function to ensure it:
- Returns actual asset key paths from Dagster (not hardcoded)
- Resolves the correct __ASSET_JOB variant from jobNames
- Fails with diagnostics when no matching asset is found

These tests mock httpx.post to isolate discovery logic from a live cluster.

This test suite covers:
- AC-1: Discovery returns actual asset key paths, not hardcoded values
- AC-2: Discovery resolves correct __ASSET_JOB variant from jobNames
- AC-3: Discovery fails with diagnostic listing available assets

Done when all fail before implementation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# The function under test. Current signature is:
#   _discover_repository_for_asset(dagster_url, asset_path) -> tuple[str, str]
# NEW expected signature (after implementation):
#   _discover_repository_for_asset(dagster_url, search_term) -> tuple[str, str, list[str], str]
#   Returns: (repo_name, location_name, asset_path, job_name)
from test_compile_deploy_materialize_e2e import _discover_repository_for_asset


def _make_graphql_response(
    asset_nodes: list[dict[str, Any]],
    status_code: int = 200,
) -> MagicMock:
    """Build a mock httpx.Response with assetNodes GraphQL payload.

    Args:
        asset_nodes: List of assetNode dicts with assetKey, repository, jobNames.
        status_code: HTTP status code for the response.

    Returns:
        MagicMock mimicking httpx.Response.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "data": {
            "assetNodes": asset_nodes,
        },
    }
    return mock_resp


def _make_asset_node(
    path: list[str],
    repo_name: str = "__repository__",
    location_name: str = "customer_360_location",
    job_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build a single assetNode dict matching Dagster GraphQL schema.

    Args:
        path: Asset key path segments.
        repo_name: Repository name hosting the asset.
        location_name: Code location name.
        job_names: List of job names the asset participates in.

    Returns:
        Dict matching Dagster assetNodes GraphQL response structure.
    """
    node: dict[str, Any] = {
        "assetKey": {"path": path},
        "repository": {
            "name": repo_name,
            "location": {"name": location_name},
        },
    }
    if job_names is not None:
        node["jobNames"] = job_names
    return node


# ---------------------------------------------------------------------------
# AC-1: Discovery returns actual asset key paths
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU2-AC-1")
def test_discovery_returns_actual_asset_path() -> None:
    """Discovery must return the real multi-segment asset key path from Dagster.

    A sloppy implementation could hardcode ["stg_crm_customers"] and pass
    simpler tests. By using a two-segment key ["customer_360", "stg_crm_customers"],
    we force the implementation to extract the path from the GraphQL response.
    """
    multi_segment_path = ["customer_360", "stg_crm_customers"]
    node = _make_asset_node(
        path=multi_segment_path,
        job_names=["__ASSET_JOB"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    # Must be a 4-tuple: (repo_name, location_name, asset_path, job_name)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 4, (
        f"Expected 4-tuple (repo, location, asset_path, job_name), "
        f"got {len(result)}-tuple: {result}"
    )

    _repo_name, _location_name, asset_path, _job_name = result
    assert asset_path == multi_segment_path, (
        f"Discovery must return actual path {multi_segment_path}, got {asset_path}. "
        "Is the path hardcoded instead of read from GraphQL response?"
    )


@pytest.mark.requirement("WU2-AC-1")
def test_discovery_returns_single_element_path() -> None:
    """Discovery handles single-element asset key paths correctly.

    Ensures the function works with both single and multi-segment paths
    and does not assume a fixed path structure.
    """
    single_path = ["stg_crm_customers"]
    node = _make_asset_node(
        path=single_path,
        job_names=["__ASSET_JOB"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    _, _, asset_path, _ = result
    assert asset_path == single_path, (
        f"Single-element path must be returned as-is: {single_path}, got {asset_path}"
    )


@pytest.mark.requirement("WU2-AC-1")
def test_discovery_matches_search_in_any_path_segment() -> None:
    """Search term must match against any segment of the asset key path.

    An asset with path ["project", "schema", "stg_crm_customers"] must
    be found when searching for "stg_crm_customers".
    """
    deep_path = ["project", "schema", "stg_crm_customers"]
    node = _make_asset_node(
        path=deep_path,
        job_names=["__ASSET_JOB"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    _, _, asset_path, _ = result
    assert asset_path == deep_path, (
        f"Must return full path {deep_path} when search matches any segment, got {asset_path}"
    )


# ---------------------------------------------------------------------------
# AC-2: Discovery resolves correct __ASSET_JOB variant
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU2-AC-2")
def test_discovery_resolves_job_name_variant() -> None:
    """Discovery must resolve __ASSET_JOB_0 (not __ASSET_JOB) from jobNames.

    Dagster creates numbered variants (__ASSET_JOB_0, __ASSET_JOB_1, etc.)
    when there are many assets. A hardcoded "__ASSET_JOB" will cause
    launchRun to fail with "pipeline not found".
    """
    node = _make_asset_node(
        path=["stg_crm_customers"],
        job_names=["__ASSET_JOB_0"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    _, _, _, job_name = result
    assert job_name == "__ASSET_JOB_0", (
        f"Must resolve to __ASSET_JOB_0 from jobNames, got '{job_name}'. "
        "Is the job name hardcoded as '__ASSET_JOB'?"
    )


@pytest.mark.requirement("WU2-AC-2")
def test_discovery_resolves_default_asset_job() -> None:
    """When jobNames includes __ASSET_JOB, prefer it over other job names.

    The __ASSET_JOB (unnumbered) variant should be preferred when present,
    as it is the canonical implicit job name.
    """
    node = _make_asset_node(
        path=["stg_crm_customers"],
        job_names=["some_other_job", "__ASSET_JOB", "another_job"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    _, _, _, job_name = result
    assert job_name == "__ASSET_JOB", (
        f"Must prefer __ASSET_JOB when present in jobNames, got '{job_name}'"
    )


@pytest.mark.requirement("WU2-AC-2")
def test_discovery_selects_numbered_variant_over_unrelated_jobs() -> None:
    """When jobNames has no exact __ASSET_JOB but has __ASSET_JOB_2, select it.

    Tests that the function filters for __ASSET_JOB* prefix and picks the
    right variant, not just the first job in the list.
    """
    node = _make_asset_node(
        path=["stg_crm_customers"],
        job_names=["scheduled_refresh", "daily_pipeline", "__ASSET_JOB_2"],
    )
    mock_response = _make_graphql_response([node])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    _, _, _, job_name = result
    assert job_name == "__ASSET_JOB_2", (
        f"Must select __ASSET_JOB_2 from jobNames, got '{job_name}'. "
        "Function must filter for __ASSET_JOB prefix."
    )


# ---------------------------------------------------------------------------
# AC-3: Fail with diagnostic when asset not found
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU2-AC-3")
def test_discovery_fails_with_diagnostic_on_missing_asset() -> None:
    """When no asset matches the search term, pytest.fail with available keys.

    The diagnostic message must list the available asset keys so the developer
    can identify typos or namespace mismatches.
    """
    available_assets = [
        _make_asset_node(path=["orders"], job_names=["__ASSET_JOB"]),
        _make_asset_node(path=["payments"], job_names=["__ASSET_JOB"]),
        _make_asset_node(path=["ns", "line_items"], job_names=["__ASSET_JOB_0"]),
    ]
    mock_response = _make_graphql_response(available_assets)

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        with pytest.raises(
            (pytest.fail.Exception, SystemExit),
        ) as exc_info:
            _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    error_msg = str(exc_info.value)
    # Must list available asset keys in the diagnostic
    assert "orders" in error_msg, (
        "Diagnostic must list available asset keys; 'orders' not found in message"
    )
    assert "payments" in error_msg, (
        "Diagnostic must list available asset keys; 'payments' not found in message"
    )
    assert "line_items" in error_msg, (
        "Diagnostic must list available asset keys; 'line_items' not found in message"
    )
    assert "stg_crm_customers" in error_msg, (
        "Diagnostic must mention the search term that was not found"
    )


@pytest.mark.requirement("WU2-AC-3")
def test_discovery_handles_empty_asset_nodes() -> None:
    """When Dagster returns zero asset nodes, pytest.fail with diagnostic.

    This covers the case where code locations are loaded but define no assets
    (misconfigured deployment).
    """
    mock_response = _make_graphql_response([])

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        with pytest.raises(
            (pytest.fail.Exception, SystemExit, RuntimeError),
        ) as exc_info:
            _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    error_msg = str(exc_info.value)
    # Must indicate no assets found, not silently return garbage
    assert (
        "stg_crm_customers" in error_msg
        or "no asset" in error_msg.lower()
        or "not found" in error_msg.lower()
    ), f"Diagnostic must indicate search term or 'no assets found', got: {error_msg}"


# ---------------------------------------------------------------------------
# AC-1+AC-2: Combo — prevents returning stale/partial data
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU2-AC-1")
@pytest.mark.requirement("WU2-AC-2")
def test_discovery_returns_correct_repo_and_location() -> None:
    """Discovery must return the correct repo/location from the matched asset.

    Prevents an implementation that returns the right path/job but wrong
    repo/location (e.g., always returning the first repo).
    """
    nodes = [
        _make_asset_node(
            path=["orders"],
            repo_name="repo_a",
            location_name="loc_a",
            job_names=["__ASSET_JOB"],
        ),
        _make_asset_node(
            path=["ns", "stg_crm_customers"],
            repo_name="repo_b",
            location_name="loc_b",
            job_names=["__ASSET_JOB_1"],
        ),
    ]
    mock_response = _make_graphql_response(nodes)

    with patch(
        "test_compile_deploy_materialize_e2e.httpx.post",
        return_value=mock_response,
    ):
        result = _discover_repository_for_asset("http://dagster:3000", "stg_crm_customers")

    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple: {result}"
    repo_name, location_name, asset_path, job_name = result
    assert repo_name == "repo_b", (
        f"Must return repo from matched asset (repo_b), not first repo. Got '{repo_name}'"
    )
    assert location_name == "loc_b", (
        f"Must return location from matched asset (loc_b). Got '{location_name}'"
    )
    assert asset_path == ["ns", "stg_crm_customers"], (
        f"Must return full path from matched asset, got {asset_path}"
    )
    assert job_name == "__ASSET_JOB_1", f"Must return job name from matched asset, got '{job_name}'"
