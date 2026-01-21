"""SemanticValidator for model relationship enforcement.

Validates semantic relationships in dbt manifest:
- FR-001: ref() resolution (FLOE-E301)
- FR-002: Circular dependency detection (FLOE-E302)
- FR-003: source() resolution (FLOE-E303)

Task: T017, T018, T019, T020
Requirements: FR-001, FR-002, FR-003, FR-004 (US1 - Semantic Model Validation)
"""

from __future__ import annotations

from collections import deque
from typing import Any

import structlog

from floe_core.enforcement.result import Violation

logger = structlog.get_logger(__name__)

# Documentation URLs for semantic violations
SEMANTIC_DOCS_BASE = "https://floe.dev/docs/enforcement/semantic"


class SemanticValidator:
    """Validates semantic relationships in dbt manifest.

    SemanticValidator checks model references, source references, and
    dependency graphs for semantic integrity. It detects:
    - Missing model references (ref() to non-existent models)
    - Missing source references (source() to undefined sources)
    - Circular dependencies between models

    Example:
        >>> from floe_core.enforcement.validators.semantic import SemanticValidator
        >>>
        >>> validator = SemanticValidator()
        >>> violations = validator.validate(manifest)
        >>> for v in violations:
        ...     print(f"{v.error_code}: {v.message}")
    """

    def __init__(self) -> None:
        """Initialize SemanticValidator."""
        self._log = logger.bind(component="SemanticValidator")

    def validate(self, manifest: dict[str, Any]) -> list[Violation]:
        """Run all semantic validation checks on manifest.

        Combines results from:
        - validate_refs(): Check model references
        - validate_sources(): Check source references
        - detect_circular_deps(): Check for cycles

        Args:
            manifest: dbt manifest dictionary with nodes, sources, child_map.

        Returns:
            List of all Violation objects found across all checks.
        """
        violations: list[Violation] = []

        # Run all semantic checks
        violations.extend(self.validate_refs(manifest))
        violations.extend(self.validate_sources(manifest))
        violations.extend(self.detect_circular_deps(manifest))

        if violations:
            self._log.info(
                "semantic_violations_found",
                count=len(violations),
                by_type={
                    "E301": sum(1 for v in violations if v.error_code == "FLOE-E301"),
                    "E302": sum(1 for v in violations if v.error_code == "FLOE-E302"),
                    "E303": sum(1 for v in violations if v.error_code == "FLOE-E303"),
                },
            )
        else:
            self._log.debug("semantic_validation_passed")

        return violations

    def validate_refs(self, manifest: dict[str, Any]) -> list[Violation]:
        """Validate model references (ref()) resolve to existing models.

        FR-001: System MUST validate model references (via ref())
        resolve to existing models in the manifest.

        Args:
            manifest: dbt manifest dictionary.

        Returns:
            List of FLOE-E301 violations for missing model references.
        """
        violations: list[Violation] = []
        nodes = manifest.get("nodes", {})

        # Build set of all valid model node IDs
        valid_model_ids: set[str] = set(nodes.keys())

        for _node_id, node in nodes.items():
            if node.get("resource_type") != "model":
                continue

            model_name = node.get("name", "unknown")
            depends_on = node.get("depends_on", {})
            dependencies = depends_on.get("nodes", [])

            for dep_id in dependencies:
                # Skip source dependencies (handled by validate_sources)
                if dep_id.startswith("source."):
                    continue

                # Check if referenced model exists
                if dep_id not in valid_model_ids:
                    # Extract missing model name from unique_id
                    missing_name = self._extract_model_name(dep_id)
                    violation = self._create_missing_ref_violation(
                        model_name=model_name,
                        missing_ref=missing_name,
                        missing_id=dep_id,
                    )
                    violations.append(violation)

        return violations

    def validate_sources(self, manifest: dict[str, Any]) -> list[Violation]:
        """Validate source references (source()) resolve to defined sources.

        FR-003: System MUST validate source references (via source())
        resolve to defined sources.

        Args:
            manifest: dbt manifest dictionary.

        Returns:
            List of FLOE-E303 violations for missing source references.
        """
        violations: list[Violation] = []
        nodes = manifest.get("nodes", {})
        sources = manifest.get("sources", {})

        # Build set of valid source IDs
        valid_source_ids: set[str] = set(sources.keys())

        for _node_id, node in nodes.items():
            if node.get("resource_type") != "model":
                continue

            model_name = node.get("name", "unknown")
            depends_on = node.get("depends_on", {})
            dependencies = depends_on.get("nodes", [])

            for dep_id in dependencies:
                # Only check source dependencies
                if not dep_id.startswith("source."):
                    continue

                # Check if source exists
                if dep_id not in valid_source_ids:
                    # Extract source info from unique_id
                    source_info = self._extract_source_info(dep_id)
                    violation = self._create_missing_source_violation(
                        model_name=model_name,
                        source_name=source_info.get("source_name", "unknown"),
                        table_name=source_info.get("table_name", "unknown"),
                        source_id=dep_id,
                    )
                    violations.append(violation)

        return violations

    def detect_circular_deps(self, manifest: dict[str, Any]) -> list[Violation]:
        """Detect circular dependencies between models.

        FR-002: System MUST detect circular dependencies between models
        and report the cycle path.

        Uses Kahn's algorithm for topological sort to detect cycles.

        Args:
            manifest: dbt manifest dictionary.

        Returns:
            List of FLOE-E302 violations for detected cycles.
        """
        violations: list[Violation] = []
        nodes = manifest.get("nodes", {})

        # Build adjacency list for models only
        model_ids: set[str] = {
            node_id for node_id, node in nodes.items() if node.get("resource_type") == "model"
        }

        # Build graph: node_id -> list of dependent node_ids
        graph: dict[str, list[str]] = {node_id: [] for node_id in model_ids}
        in_degree: dict[str, int] = dict.fromkeys(model_ids, 0)

        for node_id in model_ids:
            node = nodes[node_id]
            depends_on = node.get("depends_on", {})
            dependencies = depends_on.get("nodes", [])

            for dep_id in dependencies:
                # Only consider model dependencies
                if dep_id in model_ids:
                    graph[dep_id].append(node_id)
                    in_degree[node_id] += 1

        # Kahn's algorithm for cycle detection
        queue: deque[str] = deque()
        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)

        sorted_count = 0
        while queue:
            current = queue.popleft()
            sorted_count += 1

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If we couldn't sort all nodes, there's a cycle
        if sorted_count < len(model_ids):
            # Find nodes involved in cycle (non-zero in-degree after sort)
            cycle_nodes = [node_id for node_id, degree in in_degree.items() if degree > 0]

            if cycle_nodes:
                # Find the actual cycle path using DFS
                cycle_path = self._find_cycle_path(graph, cycle_nodes, nodes)
                violation = self._create_circular_dep_violation(cycle_path)
                violations.append(violation)

        return violations

    def _find_cycle_path(
        self,
        _graph: dict[str, list[str]],
        cycle_nodes: list[str],
        nodes: dict[str, Any],
    ) -> list[str]:
        """Find the actual cycle path using DFS.

        Args:
            _graph: Adjacency list (node -> dependents). Reserved for future use.
            cycle_nodes: Nodes involved in cycle.
            nodes: Full nodes dict for name lookup.

        Returns:
            List of model names in the cycle.
        """
        if not cycle_nodes:
            return []

        # Use DFS to find cycle starting from first cycle node
        cycle_set = set(cycle_nodes)
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node_id: str) -> list[str] | None:
            if node_id in visited:
                # Found cycle - return path from cycle start
                if node_id in path:
                    cycle_start = path.index(node_id)
                    return path[cycle_start:] + [node_id]
                return None

            visited.add(node_id)
            path.append(node_id)

            # Reverse graph: find what this node depends on
            for other_id in cycle_set:
                node = nodes.get(other_id, {})
                deps = node.get("depends_on", {}).get("nodes", [])
                if node_id in deps and other_id in cycle_set:
                    result = dfs(other_id)
                    if result:
                        return result

            path.pop()
            return None

        # Try to find cycle from each node
        for start_node in cycle_nodes:
            visited.clear()
            path.clear()
            cycle = dfs(start_node)
            if cycle:
                # Convert to model names
                return [
                    nodes.get(nid, {}).get("name", self._extract_model_name(nid)) for nid in cycle
                ]

        # Fallback: just return names of cycle nodes
        return [
            nodes.get(nid, {}).get("name", self._extract_model_name(nid))
            for nid in cycle_nodes[:5]  # Limit to 5 for readability
        ]

    def _extract_model_name(self, unique_id: str) -> str:
        """Extract model name from dbt unique_id.

        Args:
            unique_id: e.g., "model.my_project.customers"

        Returns:
            Model name, e.g., "customers"
        """
        parts = unique_id.split(".")
        return parts[-1] if parts else unique_id

    def _extract_source_info(self, unique_id: str) -> dict[str, str]:
        """Extract source info from dbt unique_id.

        Args:
            unique_id: e.g., "source.my_project.raw.orders"

        Returns:
            Dict with source_name and table_name.
        """
        parts = unique_id.split(".")
        if len(parts) >= 4:
            return {
                "source_name": parts[2],
                "table_name": parts[3],
            }
        return {
            "source_name": parts[-2] if len(parts) >= 2 else "unknown",
            "table_name": parts[-1] if parts else "unknown",
        }

    def _create_missing_ref_violation(
        self,
        model_name: str,
        missing_ref: str,
        missing_id: str,
    ) -> Violation:
        """Create FLOE-E301 violation for missing model reference.

        Args:
            model_name: Model that has the invalid ref.
            missing_ref: Name of the missing model.
            missing_id: Full unique_id of missing model.

        Returns:
            Violation with actionable details.
        """
        return Violation(
            error_code="FLOE-E301",
            severity="error",
            policy_type="semantic",
            model_name=model_name,
            message=f"Model '{model_name}' references non-existent model '{missing_ref}'",
            expected=f"Model '{missing_ref}' should exist in the manifest",
            actual=f"ref('{missing_ref}') resolves to nothing (ID: {missing_id})",
            suggestion=(
                f"Create the model '{missing_ref}' or update the ref() call in "
                f"'{model_name}' to reference an existing model."
            ),
            documentation_url=f"{SEMANTIC_DOCS_BASE}#missing-ref",
        )

    def _create_missing_source_violation(
        self,
        model_name: str,
        source_name: str,
        table_name: str,
        source_id: str,
    ) -> Violation:
        """Create FLOE-E303 violation for missing source reference.

        Args:
            model_name: Model that has the invalid source.
            source_name: Name of the source.
            table_name: Name of the table in source.
            source_id: Full unique_id of missing source.

        Returns:
            Violation with actionable details.
        """
        return Violation(
            error_code="FLOE-E303",
            severity="error",
            policy_type="semantic",
            model_name=model_name,
            message=(
                f"Model '{model_name}' references undefined source '{source_name}.{table_name}'"
            ),
            expected=f"Source '{source_name}.{table_name}' should be defined in a sources.yml file",
            actual=f"source('{source_name}', '{table_name}') resolves to nothing (ID: {source_id})",
            suggestion=(
                f"Define the source in a _sources.yml file:\n"
                f"  sources:\n"
                f"    - name: {source_name}\n"
                f"      tables:\n"
                f"        - name: {table_name}"
            ),
            documentation_url=f"{SEMANTIC_DOCS_BASE}#missing-source",
        )

    def _create_circular_dep_violation(
        self,
        cycle_path: list[str],
    ) -> Violation:
        """Create FLOE-E302 violation for circular dependency.

        Args:
            cycle_path: List of model names in the cycle.

        Returns:
            Violation with actionable details.
        """
        cycle_str = " -> ".join(cycle_path)
        first_model = cycle_path[0] if cycle_path else "unknown"

        return Violation(
            error_code="FLOE-E302",
            severity="error",
            policy_type="semantic",
            model_name=first_model,
            message=f"Circular dependency detected: {cycle_str}",
            expected="Model dependencies should form a directed acyclic graph (DAG)",
            actual=f"Cycle found involving models: {', '.join(cycle_path)}",
            suggestion=(
                "Break the circular dependency by:\n"
                "1. Identifying which model should logically come first\n"
                "2. Removing the ref() that creates the cycle\n"
                "3. Consider using an intermediate model or restructuring the DAG"
            ),
            documentation_url=f"{SEMANTIC_DOCS_BASE}#circular-dependency",
        )


__all__ = ["SemanticValidator"]
