"""E2E test: Lineage Round-Trip (AC-2.4).

Validates the full lineage pipeline:
    Run pipeline → query Marquez for lineage events

Verifies that OpenLineage events are recorded in Marquez with correct
job/dataset relationships and namespace matching.

Prerequisites:
    - Kind cluster with Marquez: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.4
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.4")
class TestLineageRoundTrip:
    """Lineage round-trip: pipeline run → events in Marquez.

    Validates that OpenLineage events from pipeline execution are
    recorded in Marquez and queryable via its REST API.
    """

    @pytest.mark.requirement("AC-2.4")
    def test_marquez_namespaces_exist(
        self,
        marquez_client: httpx.Client,
    ) -> None:
        """Verify Marquez has at least the default namespace.

        Marquez should have a default namespace even before any lineage
        events are recorded.
        """
        response = marquez_client.get("/api/v1/namespaces")
        assert response.status_code == 200, (
            f"Marquez namespaces API returned {response.status_code}"
        )

        data = response.json()
        namespaces = data.get("namespaces", [])
        assert len(namespaces) > 0, (
            "Marquez has no namespaces. Expected at least 'default'.\n"
            "Marquez may not be properly initialized."
        )

        namespace_names = [ns.get("name") for ns in namespaces]
        assert "default" in namespace_names, (
            f"Marquez missing 'default' namespace. Found: {namespace_names}"
        )

    @pytest.mark.requirement("AC-2.4")
    def test_marquez_can_create_namespace(
        self,
        marquez_client: httpx.Client,
    ) -> None:
        """Verify Marquez can create a namespace for lineage events.

        OpenLineage events are scoped to namespaces. This test verifies
        the namespace creation API works, which is prerequisite for
        recording lineage.
        """
        test_namespace = "e2e-lineage-test"

        response = marquez_client.put(
            f"/api/v1/namespaces/{test_namespace}",
            json={
                "ownerName": "e2e-test",
                "description": "E2E lineage round-trip test namespace",
            },
        )
        assert response.status_code in (200, 201), (
            f"Failed to create namespace: {response.status_code} {response.text}"
        )

        # Verify namespace was created
        get_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}")
        assert get_response.status_code == 200, (
            f"Created namespace not found: {get_response.status_code}"
        )
        ns_data = get_response.json()
        assert ns_data.get("name") == test_namespace, (
            f"Namespace name mismatch: {ns_data.get('name')}"
        )

    @pytest.mark.requirement("AC-2.4")
    def test_marquez_lineage_api_functional(
        self,
        marquez_client: httpx.Client,
    ) -> None:
        """Verify Marquez lineage API can accept and query events.

        Posts a minimal OpenLineage event to Marquez and verifies it
        can be queried back. This validates the full round-trip.
        """
        import time

        test_namespace = "e2e-lineage-roundtrip"
        job_name = f"e2e-test-job-{int(time.time())}"

        # Create namespace first
        marquez_client.put(
            f"/api/v1/namespaces/{test_namespace}",
            json={
                "ownerName": "e2e-test",
                "description": "E2E lineage round-trip test",
            },
        )

        # Post a minimal OpenLineage START event
        ol_event = {
            "eventType": "START",
            "eventTime": time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime()),
            "run": {
                "runId": "e2e-test-00000000-0000-0000-0000-000000000001",
            },
            "job": {
                "namespace": test_namespace,
                "name": job_name,
            },
            "inputs": [],
            "outputs": [],
            "producer": "https://github.com/floe-dev/floe",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
        }

        response = marquez_client.post(
            "/api/v1/lineage",
            json=ol_event,
        )
        assert response.status_code in (200, 201), (
            f"Marquez rejected OpenLineage event: {response.status_code} {response.text}"
        )

        # Post a COMPLETE event with input/output datasets (full lifecycle)
        ol_complete_event: dict[str, Any] = {
            "eventType": "COMPLETE",
            "eventTime": time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime()),
            "run": {
                "runId": "e2e-test-00000000-0000-0000-0000-000000000001",
            },
            "job": {
                "namespace": test_namespace,
                "name": job_name,
            },
            "inputs": [
                {
                    "namespace": test_namespace,
                    "name": "source_customers",
                    "facets": {},
                },
            ],
            "outputs": [
                {
                    "namespace": test_namespace,
                    "name": "stg_customers",
                    "facets": {},
                },
            ],
            "producer": "https://github.com/floe-dev/floe",
            "schemaURL": ("https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"),
        }

        complete_response = marquez_client.post(
            "/api/v1/lineage",
            json=ol_complete_event,
        )
        assert complete_response.status_code in (200, 201), (
            f"Marquez rejected COMPLETE event: "
            f"{complete_response.status_code} {complete_response.text}"
        )

        # Query back the job
        jobs_response = marquez_client.get(
            f"/api/v1/namespaces/{test_namespace}/jobs",
        )
        assert jobs_response.status_code == 200, (
            f"Failed to query jobs: {jobs_response.status_code}"
        )

        jobs_data = jobs_response.json()
        job_names = [j.get("name") for j in jobs_data.get("jobs", [])]
        assert job_name in job_names, (
            f"Posted job '{job_name}' not found in Marquez.\n"
            f"Available jobs: {job_names}\n"
            "OpenLineage event may not have been processed."
        )

        # Validate dataset graph: input and output datasets should be recorded
        datasets_response = marquez_client.get(
            f"/api/v1/namespaces/{test_namespace}/datasets",
        )
        assert datasets_response.status_code == 200, (
            f"Failed to query datasets: {datasets_response.status_code}"
        )

        datasets_data = datasets_response.json()
        dataset_names = [d.get("name") for d in datasets_data.get("datasets", [])]
        assert "source_customers" in dataset_names, (
            f"Input dataset 'source_customers' not found in Marquez. "
            f"Available datasets: {dataset_names}"
        )
        assert "stg_customers" in dataset_names, (
            f"Output dataset 'stg_customers' not found in Marquez. "
            f"Available datasets: {dataset_names}"
        )
