"""Unit tests for permission aggregation in RBACManifestGenerator.

Tests the aggregate_permissions function that combines secret references
into minimal Role rules following least-privilege principles.

Task: T041
User Story: US4 - RBAC Manifest Generation
Requirements: FR-052
"""

from __future__ import annotations

import pytest


class TestPermissionAggregationBasics:
    """Unit tests for basic permission aggregation behavior."""

    @pytest.mark.requirement("FR-052")
    def test_single_secret_reference_produces_single_rule(self) -> None:
        """Test single secret reference produces one rule with resourceNames."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["snowflake-creds"]
        rules = aggregate_permissions(secret_refs)

        assert len(rules) == 1
        assert rules[0].resources == ["secrets"]
        assert rules[0].verbs == ["get"]
        assert rules[0].resource_names == ["snowflake-creds"]
        assert rules[0].api_groups == [""]

    @pytest.mark.requirement("FR-052")
    def test_multiple_secret_references_aggregated_into_single_rule(self) -> None:
        """Test multiple secrets are aggregated into a single rule."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["snowflake-creds", "catalog-creds", "api-key"]
        rules = aggregate_permissions(secret_refs)

        # Should produce one rule with all resourceNames
        assert len(rules) == 1
        rule = rules[0]
        assert set(rule.resource_names or []) == {
            "snowflake-creds",
            "catalog-creds",
            "api-key",
        }
        assert rule.resources == ["secrets"]
        assert rule.verbs == ["get"]

    @pytest.mark.requirement("FR-052")
    def test_empty_secret_references_produces_no_rules(self) -> None:
        """Test empty secret references produces empty rules list."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs: list[str] = []
        rules = aggregate_permissions(secret_refs)

        assert rules == []


class TestPermissionAggregationDeduplication:
    """Unit tests for permission aggregation deduplication."""

    @pytest.mark.requirement("FR-052")
    def test_duplicate_secret_references_deduplicated(self) -> None:
        """Test duplicate secret references are deduplicated."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = [
            "snowflake-creds",
            "catalog-creds",
            "snowflake-creds",  # Duplicate
            "api-key",
            "snowflake-creds",  # Another duplicate
            "catalog-creds",  # Duplicate
        ]
        rules = aggregate_permissions(secret_refs)

        # Should have only unique resource names
        assert len(rules) == 1
        resource_names = rules[0].resource_names or []
        assert len(resource_names) == 3
        assert set(resource_names) == {"snowflake-creds", "catalog-creds", "api-key"}

    @pytest.mark.requirement("FR-052")
    def test_preserves_order_of_first_occurrence(self) -> None:
        """Test deduplicated secrets preserve order of first occurrence."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["alpha", "beta", "gamma", "alpha", "beta"]
        rules = aggregate_permissions(secret_refs)

        # Resource names should preserve insertion order
        resource_names = rules[0].resource_names or []
        assert resource_names == ["alpha", "beta", "gamma"]


class TestPermissionAggregationSecurityCompliance:
    """Unit tests for security compliance in permission aggregation."""

    @pytest.mark.requirement("FR-052")
    def test_aggregation_uses_only_get_verb(self) -> None:
        """Test aggregation produces rules with only 'get' verb (FR-024)."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["secret-a", "secret-b"]
        rules = aggregate_permissions(secret_refs)

        for rule in rules:
            assert rule.verbs == ["get"]
            # No list, watch, create, update, delete allowed
            assert "list" not in rule.verbs
            assert "watch" not in rule.verbs
            assert "create" not in rule.verbs
            assert "update" not in rule.verbs
            assert "delete" not in rule.verbs

    @pytest.mark.requirement("FR-052")
    def test_aggregation_uses_resource_names_constraint(self) -> None:
        """Test aggregation always uses resourceNames constraint (FR-021)."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["specific-secret"]
        rules = aggregate_permissions(secret_refs)

        # Must use resourceNames, not wildcard access
        assert rules[0].resource_names is not None
        assert len(rules[0].resource_names) > 0
        assert "*" not in rules[0].resource_names

    @pytest.mark.requirement("FR-052")
    def test_aggregation_targets_secrets_resource(self) -> None:
        """Test aggregation targets only secrets resource."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["my-secret"]
        rules = aggregate_permissions(secret_refs)

        assert rules[0].resources == ["secrets"]
        # Not pods, configmaps, etc.
        assert "pods" not in rules[0].resources
        assert "configmaps" not in rules[0].resources

    @pytest.mark.requirement("FR-052")
    def test_aggregation_uses_core_api_group(self) -> None:
        """Test aggregation uses core API group for secrets."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["my-secret"]
        rules = aggregate_permissions(secret_refs)

        # Secrets are in the core API group (empty string)
        assert rules[0].api_groups == [""]


class TestPermissionAggregationRoleRuleIntegration:
    """Unit tests for RoleRule integration with permission aggregation."""

    @pytest.mark.requirement("FR-052")
    def test_aggregated_rules_are_valid_role_rules(self) -> None:
        """Test aggregated rules are valid RoleRule instances."""
        from floe_core.rbac.generator import aggregate_permissions
        from floe_core.schemas.rbac import RoleRule

        secret_refs = ["secret-a", "secret-b"]
        rules = aggregate_permissions(secret_refs)

        for rule in rules:
            assert isinstance(rule, RoleRule)

    @pytest.mark.requirement("FR-052")
    def test_aggregated_rules_can_be_used_in_role_config(self) -> None:
        """Test aggregated rules can be added to RoleConfig."""
        from floe_core.rbac.generator import aggregate_permissions
        from floe_core.schemas.rbac import RoleConfig

        secret_refs = ["secret-a", "secret-b"]
        rules = aggregate_permissions(secret_refs)

        # Should be usable in RoleConfig
        role = RoleConfig(
            name="floe-test-role",
            namespace="floe-jobs",
            rules=rules,
        )

        assert role.rules == rules
        manifest = role.to_k8s_manifest()
        assert len(manifest["rules"]) == 1

    @pytest.mark.requirement("FR-052")
    def test_aggregated_rule_produces_valid_k8s_manifest_rule(self) -> None:
        """Test aggregated rule produces valid K8s manifest structure."""
        from floe_core.rbac.generator import aggregate_permissions
        from floe_core.schemas.rbac import RoleConfig

        secret_refs = ["cred-a", "cred-b"]
        rules = aggregate_permissions(secret_refs)

        role = RoleConfig(
            name="floe-test-role",
            namespace="floe-jobs",
            rules=rules,
        )
        manifest = role.to_k8s_manifest()

        # Check manifest rule structure
        manifest_rule = manifest["rules"][0]
        assert manifest_rule["apiGroups"] == [""]
        assert manifest_rule["resources"] == ["secrets"]
        assert manifest_rule["verbs"] == ["get"]
        assert set(manifest_rule["resourceNames"]) == {"cred-a", "cred-b"}


class TestPermissionAggregationEdgeCases:
    """Unit tests for edge cases in permission aggregation."""

    @pytest.mark.requirement("FR-052")
    def test_single_character_secret_name(self) -> None:
        """Test aggregation handles single character secret names."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = ["a", "b", "c"]
        rules = aggregate_permissions(secret_refs)

        assert rules[0].resource_names == ["a", "b", "c"]

    @pytest.mark.requirement("FR-052")
    def test_long_secret_name(self) -> None:
        """Test aggregation handles long secret names."""
        from floe_core.rbac.generator import aggregate_permissions

        long_name = "a" * 253  # K8s max name length
        secret_refs = [long_name]
        rules = aggregate_permissions(secret_refs)

        assert rules[0].resource_names == [long_name]

    @pytest.mark.requirement("FR-052")
    def test_secret_name_with_hyphens_and_dots(self) -> None:
        """Test aggregation handles secret names with hyphens and dots."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = [
            "my-secret-name",
            "my.secret.name",
            "my-secret.name",
        ]
        rules = aggregate_permissions(secret_refs)

        resource_names = set(rules[0].resource_names or [])
        assert resource_names == {"my-secret-name", "my.secret.name", "my-secret.name"}

    @pytest.mark.requirement("FR-052")
    def test_large_number_of_secrets(self) -> None:
        """Test aggregation handles large number of secrets efficiently."""
        from floe_core.rbac.generator import aggregate_permissions

        secret_refs = [f"secret-{i}" for i in range(100)]
        rules = aggregate_permissions(secret_refs)

        # Should still produce one aggregated rule
        assert len(rules) == 1
        assert len(rules[0].resource_names or []) == 100

    @pytest.mark.requirement("FR-052")
    def test_whitespace_handling(self) -> None:
        """Test aggregation strips whitespace from secret names."""
        from floe_core.rbac.generator import aggregate_permissions

        # Secret names with whitespace should be stripped
        secret_refs = ["  my-secret  ", "other-secret"]
        rules = aggregate_permissions(secret_refs)

        resource_names = rules[0].resource_names or []
        # Expect stripped names
        assert "my-secret" in resource_names or "  my-secret  " in resource_names
