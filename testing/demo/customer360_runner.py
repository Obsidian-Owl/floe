"""Launch the Customer 360 demo through Dagster GraphQL."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

DEFAULT_VALIDATION_MANIFEST = Path("demo/customer-360/validation.yaml")
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
SUCCESS_STATUSES = {"SUCCESS"}
TERMINAL_FAILURE_STATUSES = {"FAILURE", "CANCELED"}

GraphQLClient = Callable[[str, dict[str, Any]], dict[str, Any]]
Sleep = Callable[[float], None]


class RunnerError(RuntimeError):
    """Raised when the Customer 360 Dagster run cannot be launched or completed."""


@dataclass(frozen=True)
class Customer360RunConfig:
    """Dagster launch configuration loaded from the validation manifest."""

    namespace: str
    dagster_url: str
    job_name: str
    run_tags: dict[str, str]


@dataclass(frozen=True)
class Customer360RunResult:
    """Customer 360 Dagster run result."""

    status: str
    run_id: str
    job_name: str


@dataclass(frozen=True)
class DagsterRepository:
    """Dagster repository/location containing the configured Customer 360 job."""

    repository_name: str
    location_name: str


class Customer360DagsterRunner:
    """Load Customer 360 demo config, launch Dagster, and wait for completion."""

    def __init__(
        self,
        *,
        graphql_client: GraphQLClient | None = None,
        sleep: Sleep = time.sleep,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._graphql = graphql_client or default_graphql_client
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def run(self, manifest_path: Path = DEFAULT_VALIDATION_MANIFEST) -> Customer360RunResult:
        """Launch the configured Customer 360 Dagster job and print deterministic output."""
        config = load_customer360_run_config(manifest_path)
        graphql_url = _join_url(config.dagster_url, "graphql")

        try:
            repository = self._discover_repository(graphql_url, config.job_name)
            run_id = self._launch_run(graphql_url, config, repository)
            status = self._poll_run(graphql_url, run_id)
        except RunnerError as exc:
            _print_failure(config=config, error=str(exc))
            raise

        result = Customer360RunResult(status="PASS", run_id=run_id, job_name=config.job_name)
        print("status=PASS")
        print(f"dagster.run_id={result.run_id}")
        print(f"dagster.job_name={result.job_name}")
        if status not in SUCCESS_STATUSES:
            raise RunnerError(f"Dagster run completed with unexpected status {status}")
        return result

    def _discover_repository(self, graphql_url: str, job_name: str) -> DagsterRepository:
        response = self._request(
            graphql_url,
            {
                "query": DISCOVER_REPOSITORIES_QUERY,
                "variables": {},
            },
        )
        repositories = response.get("data", {}).get("repositoriesOrError")
        if not isinstance(repositories, dict):
            raise RunnerError("Dagster repository discovery returned an invalid response")
        if repositories.get("__typename") != "RepositoryConnection":
            message = _dagster_error_message(repositories)
            raise RunnerError(f"Dagster repository discovery failed: {message}")

        for node in repositories.get("nodes", []):
            if not isinstance(node, dict):
                continue
            names = _repository_job_names(node)
            if job_name in names:
                location = node.get("location")
                if not isinstance(location, dict) or not location.get("name"):
                    raise RunnerError(
                        "Dagster repository discovery did not include a location name"
                    )
                repository_name = node.get("name")
                if not isinstance(repository_name, str) or not repository_name.strip():
                    raise RunnerError(
                        "Dagster repository discovery did not include a repository name"
                    )
                return DagsterRepository(
                    repository_name=repository_name,
                    location_name=str(location["name"]),
                )

        raise RunnerError("Dagster job was not found")

    def _launch_run(
        self,
        graphql_url: str,
        config: Customer360RunConfig,
        repository: DagsterRepository,
    ) -> str:
        response = self._request(
            graphql_url,
            {
                "query": LAUNCH_RUN_MUTATION,
                "variables": {
                    "executionParams": {
                        "selector": {
                            "repositoryLocationName": repository.location_name,
                            "repositoryName": repository.repository_name,
                            "pipelineName": config.job_name,
                        },
                        "runConfigData": {},
                        "mode": "default",
                        "executionMetadata": {
                            "tags": [
                                {"key": key, "value": value}
                                for key, value in sorted(config.run_tags.items())
                            ],
                        },
                    }
                },
            },
        )
        result = response.get("data", {}).get("launchPipelineExecution")
        if not isinstance(result, dict):
            raise RunnerError("Dagster launch returned an invalid response")
        if result.get("__typename") != "LaunchRunSuccess":
            message = _dagster_error_message(result)
            raise RunnerError(f"Dagster launch failed: {message}")

        run = result.get("run")
        if not isinstance(run, dict):
            raise RunnerError("Dagster launch did not return a run id")
        run_id_value = run.get("runId")
        if not isinstance(run_id_value, str):
            raise RunnerError("Dagster launch did not return a run id")
        return run_id_value

    def _poll_run(self, graphql_url: str, run_id: str) -> str:
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            response = self._request(
                graphql_url,
                {
                    "query": RUN_STATUS_QUERY,
                    "variables": {"runId": run_id},
                },
            )
            result = response.get("data", {}).get("runOrError")
            if not isinstance(result, dict):
                raise RunnerError("Dagster run status returned an invalid response")
            if result.get("__typename") != "Run":
                message = _dagster_error_message(result)
                raise RunnerError(f"Dagster run status failed: {message}")

            status = result.get("status")
            if status in SUCCESS_STATUSES:
                return str(status)
            if status in TERMINAL_FAILURE_STATUSES:
                raise RunnerError(f"Dagster run {run_id} finished with status {status}")
            if time.monotonic() >= deadline:
                raise RunnerError(f"Dagster run {run_id} timed out with status {status}")
            self._sleep(self._poll_interval_seconds)

    def _request(self, graphql_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._graphql(graphql_url, payload)
        if response.get("errors"):
            raise RunnerError(f"Dagster GraphQL returned errors: {response['errors']}")
        return response


def default_graphql_client(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST a GraphQL request to Dagster and return the decoded JSON response."""
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RunnerError(f"Dagster GraphQL request failed: {exc}") from exc

    try:
        decoded = response.json()
    except ValueError as exc:
        raise RunnerError(f"Dagster GraphQL returned invalid JSON from {url}") from exc

    if not isinstance(decoded, dict):
        raise RunnerError("Dagster GraphQL returned a non-object response")
    return decoded


def load_customer360_run_config(path: Path) -> Customer360RunConfig:
    """Load Dagster run configuration from the Customer 360 validation manifest."""
    with path.open(encoding="utf-8") as manifest_file:
        raw_manifest = yaml.safe_load(manifest_file) or {}
    if not isinstance(raw_manifest, dict):
        raise ValueError(f"Customer 360 validation manifest must be a mapping: {path}")

    validation = _mapping(raw_manifest.get("validation"), "validation")
    urls = _mapping(validation.get("urls"), "validation.urls")
    dagster = _mapping(validation.get("dagster"), "validation.dagster")
    return Customer360RunConfig(
        namespace=_string(validation.get("namespace"), "validation.namespace", default="floe-dev"),
        dagster_url=_string(urls.get("dagster"), "validation.urls.dagster"),
        job_name=_string(dagster.get("job_name"), "validation.dagster.job_name"),
        run_tags=_string_mapping(dagster.get("run_tags"), "validation.dagster.run_tags"),
    )


def _print_failure(*, config: Customer360RunConfig, error: str) -> None:
    print("status=FAIL")
    print(f"dagster.url={config.dagster_url}")
    print(f"dagster.job_name={config.job_name}")
    print(
        f"diagnostic=kubectl logs -n {config.namespace} deployment/floe-platform-dagster-webserver"
    )
    print(f"error={error}")


def _repository_job_names(repository: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("jobs", "pipelines"):
        for item in repository.get(key, []):
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.add(item["name"])
    return names


def _dagster_error_message(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, str):
        return message
    if isinstance(payload.get("errors"), list):
        return "; ".join(str(error.get("message", error)) for error in payload["errors"])
    return str(payload.get("__typename", "unknown error"))


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _string(value: object, name: str, *, default: str | None = None) -> str:
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{name} is required")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _string_mapping(value: object, name: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a non-empty mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{name} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name}.{key} must be a non-empty string")
        result[key.strip()] = item.strip()
    return result


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


DISCOVER_REPOSITORIES_QUERY = """
query Customer360Repositories {
  repositoriesOrError {
    __typename
    ... on RepositoryConnection {
      nodes {
        name
        location { name }
        pipelines { name }
      }
    }
    ... on PythonError {
      message
    }
  }
}
"""

LAUNCH_RUN_MUTATION = """
mutation LaunchCustomer360Run($executionParams: ExecutionParams!) {
  launchPipelineExecution(executionParams: $executionParams) {
    __typename
    ... on LaunchRunSuccess {
      run { runId }
    }
    ... on PipelineNotFoundError {
      message
    }
    ... on RunConfigValidationInvalid {
      errors { message }
    }
    ... on PythonError {
      message
    }
  }
}
"""

RUN_STATUS_QUERY = """
query Customer360RunStatus($runId: ID!) {
  runOrError(runId: $runId) {
    __typename
    ... on Run {
      runId
      status
    }
    ... on RunNotFoundError {
      message
    }
    ... on PythonError {
      message
    }
  }
}
"""
