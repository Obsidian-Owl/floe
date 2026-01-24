"""Unit tests for contract inheritance validation.

Task: T036, T037, T038, T038b
Requirements: FR-011 (Three-tier inheritance), FR-012 (SLA weakening),
              FR-013 (Classification weakening), FR-014 (FLOE-E510 error)

Tests for inheritance rules:
- Child contracts cannot weaken parent SLA properties (freshness, availability, quality)
- Child contracts cannot remove/weaken field classifications (e.g., PII to public)
- Three-tier hierarchy: enterprise -> domain -> product
- Circular dependency detection
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import from module that will be created
# from floe_core.enforcement.validators.inheritance import InheritanceValidator


class TestSLAWeakeningDetection:
    """Tests for SLA weakening detection (FR-012, FR-014).

    Task: T036
    """

    @pytest.mark.requirement("3C-FR-012")
    def test_weaker_freshness_sla_detected(self) -> None:
        """Test that weakening freshness SLA (PT6H -> PT12H) is detected.

        Parent: freshness = PT6H (6 hours)
        Child: freshness = PT12H (12 hours - weaker, data can be older)

        Expected: FLOE-E510 error
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT12H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        # Import here to avoid import errors before implementation
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E510"
        assert "freshness" in violation.message.lower()
        assert "PT6H" in violation.message or "6" in violation.message

    @pytest.mark.requirement("3C-FR-012")
    def test_weaker_availability_sla_detected(self) -> None:
        """Test that weakening availability SLA (99.9% -> 99%) is detected.

        Parent: availability = 99.9%
        Child: availability = 99% (weaker)

        Expected: FLOE-E510 error
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: availability
    value: 99.9%
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: availability
    value: 99%
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E510"
        assert "availability" in violation.message.lower()

    @pytest.mark.requirement("3C-FR-012")
    def test_stronger_freshness_sla_allowed(self) -> None:
        """Test that strengthening freshness SLA (PT6H -> PT1H) is allowed.

        Parent: freshness = PT6H (6 hours)
        Child: freshness = PT1H (1 hour - stronger, data is fresher)

        Expected: Valid (strengthening is allowed)
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT1H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3C-FR-012")
    def test_equal_sla_allowed(self) -> None:
        """Test that matching SLA values are allowed.

        Parent: freshness = PT6H
        Child: freshness = PT6H (same)

        Expected: Valid
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3C-FR-012")
    def test_missing_required_sla_detected(self) -> None:
        """Test that missing a parent-required SLA is detected.

        Parent: freshness = PT6H
        Child: no freshness SLA (missing required SLA)

        Expected: FLOE-E510 error
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E510"
        assert "freshness" in violation.message.lower()


class TestClassificationWeakeningDetection:
    """Tests for classification weakening detection (FR-013).

    Task: T037
    """

    @pytest.mark.requirement("3C-FR-013")
    def test_pii_to_public_classification_weakening_detected(self) -> None:
        """Test that weakening classification (pii -> public) is detected.

        Parent: field 'email' has classification 'pii'
        Child: field 'email' has classification 'public' (weaker)

        Expected: FLOE-E511 error (classification weakening)
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
        classification: pii
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
        classification: public
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        # Classification errors use FLOE-E511
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E511"
        assert "email" in violation.message
        assert "classification" in violation.message.lower()

    @pytest.mark.requirement("3C-FR-013")
    def test_removed_classification_detected(self) -> None:
        """Test that removing a classification from a parent-classified field is detected.

        Parent: field 'email' has classification 'pii'
        Child: field 'email' has no classification (removed)

        Expected: FLOE-E511 error
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
        classification: pii
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        violation = result.violations[0]
        assert violation.error_code == "FLOE-E511"

    @pytest.mark.requirement("3C-FR-013")
    def test_strengthened_classification_allowed(self) -> None:
        """Test that strengthening classification is allowed.

        Parent: field 'email' has classification 'internal'
        Child: field 'email' has classification 'pii' (stronger)

        Expected: Valid (strengthening is allowed)
        """
        parent_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
        classification: internal
"""
        child_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: email
        logicalType: string
        classification: pii
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        assert result.valid is True
        assert len(result.violations) == 0


class TestThreeTierInheritance:
    """Tests for three-tier inheritance (FR-011).

    Task: T038
    """

    @pytest.mark.requirement("3C-FR-011")
    def test_enterprise_domain_product_chain_valid(self) -> None:
        """Test valid three-tier inheritance chain.

        Enterprise: freshness = PT24H
        Domain: freshness = PT12H (stronger)
        Product: freshness = PT6H (even stronger)

        Expected: Valid (each level strengthens)
        """
        enterprise_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT24H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        domain_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: domain-contract
version: 1.0.0
name: domain-contract
status: active
slaProperties:
  - property: freshness
    value: PT12H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        product_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()

        # Validate domain against enterprise
        result1 = validator.validate_inheritance(
            parent_yaml=enterprise_yaml,
            child_yaml=domain_yaml,
        )
        assert result1.valid is True

        # Validate product against domain
        result2 = validator.validate_inheritance(
            parent_yaml=domain_yaml,
            child_yaml=product_yaml,
        )
        assert result2.valid is True

    @pytest.mark.requirement("3C-FR-011")
    def test_product_cannot_skip_domain_requirements(self) -> None:
        """Test that product must meet domain requirements, not just enterprise.

        Enterprise: freshness = PT24H
        Domain: freshness = PT6H (stronger than enterprise)
        Product: freshness = PT12H (weaker than domain, but stronger than enterprise)

        Expected: Invalid when validating product against domain
        """
        domain_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: domain-contract
version: 1.0.0
name: domain-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        product_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT12H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        validator = InheritanceValidator()
        result = validator.validate_inheritance(
            parent_yaml=domain_yaml,
            child_yaml=product_yaml,
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        assert result.violations[0].error_code == "FLOE-E510"


class TestContractValidatorInheritanceIntegration:
    """Tests for ContractValidator.validate_with_inheritance().

    Task: T045
    """

    @pytest.fixture
    def parent_contract_file(self, tmp_path: Path) -> Path:
        """Create a parent contract with strict SLA."""
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: enterprise-contract
version: 1.0.0
name: enterprise-contract
status: active
slaProperties:
  - property: freshness
    value: PT6H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        contract_path = tmp_path / "parent-contract.yaml"
        contract_path.write_text(contract_yaml)
        return contract_path

    @pytest.fixture
    def valid_child_contract_file(self, tmp_path: Path) -> Path:
        """Create a child contract with stronger SLA (valid)."""
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT1H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        contract_path = tmp_path / "valid-child-contract.yaml"
        contract_path.write_text(contract_yaml)
        return contract_path

    @pytest.fixture
    def invalid_child_contract_file(self, tmp_path: Path) -> Path:
        """Create a child contract with weaker SLA (invalid)."""
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: product-contract
version: 1.0.0
name: product-contract
status: active
slaProperties:
  - property: freshness
    value: PT12H
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
"""
        contract_path = tmp_path / "invalid-child-contract.yaml"
        contract_path.write_text(contract_yaml)
        return contract_path

    @pytest.mark.requirement("3C-FR-011")
    def test_validate_with_inheritance_passes_for_stronger_sla(
        self,
        parent_contract_file: Path,
        valid_child_contract_file: Path,
    ) -> None:
        """Test that valid child (stronger SLA) passes inheritance validation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()
        result = validator.validate_with_inheritance(
            contract_path=valid_child_contract_file,
            parent_contract_path=parent_contract_file,
            enforcement_level="strict",
        )

        assert result.valid is True
        assert len(result.violations) == 0

    @pytest.mark.requirement("3C-FR-012")
    def test_validate_with_inheritance_fails_for_weaker_sla(
        self,
        parent_contract_file: Path,
        invalid_child_contract_file: Path,
    ) -> None:
        """Test that invalid child (weaker SLA) fails inheritance validation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()
        result = validator.validate_with_inheritance(
            contract_path=invalid_child_contract_file,
            parent_contract_path=parent_contract_file,
            enforcement_level="strict",
        )

        assert result.valid is False
        assert len(result.violations) >= 1
        # Should have FLOE-E510 for SLA weakening
        error_codes = [v.error_code for v in result.violations]
        assert "FLOE-E510" in error_codes

    @pytest.mark.requirement("3C-FR-011")
    def test_validate_with_inheritance_no_parent(
        self,
        valid_child_contract_file: Path,
    ) -> None:
        """Test that validation works without parent contract."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()
        result = validator.validate_with_inheritance(
            contract_path=valid_child_contract_file,
            parent_contract_path=None,
            enforcement_level="strict",
        )

        # Should still validate ODCS compliance
        assert result.valid is True


class TestCircularDependencyDetection:
    """Tests for circular contract dependency detection.

    Task: T038b
    Requirements: FR-011 (inheritance chain validation includes cycle detection)

    Circular dependencies occur when:
    - A inherits from B, B inherits from A (direct cycle)
    - A inherits from B, B inherits from C, C inherits from A (indirect cycle)
    """

    @pytest.mark.requirement("3C-FR-011")
    def test_direct_circular_dependency_detected(self) -> None:
        """Test that direct A -> B -> A cycle is detected.

        Contract A inherits from B
        Contract B inherits from A

        Expected: FLOE-E512 error with cycle path
        """
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        # Build a contract chain where A inherits from B
        contracts = {
            "contract-a": {
                "id": "contract-a",
                "inherits_from": "contract-b",
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-a
version: 1.0.0
name: contract-a
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
            "contract-b": {
                "id": "contract-b",
                "inherits_from": "contract-a",  # Creates cycle!
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-b
version: 1.0.0
name: contract-b
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
        }

        validator = InheritanceValidator()
        result = validator.detect_circular_dependencies(
            contract_id="contract-a",
            contracts=contracts,
        )

        assert result.has_cycle is True
        assert result.cycle_path is not None
        assert len(result.cycle_path) >= 2
        assert "contract-a" in result.cycle_path
        assert "contract-b" in result.cycle_path

    @pytest.mark.requirement("3C-FR-011")
    def test_indirect_circular_dependency_detected(self) -> None:
        """Test that indirect A -> B -> C -> A cycle is detected.

        Contract A inherits from B
        Contract B inherits from C
        Contract C inherits from A

        Expected: FLOE-E512 error with full cycle path
        """
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        contracts = {
            "contract-a": {
                "id": "contract-a",
                "inherits_from": "contract-b",
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-a
version: 1.0.0
name: contract-a
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
            "contract-b": {
                "id": "contract-b",
                "inherits_from": "contract-c",
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-b
version: 1.0.0
name: contract-b
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
            "contract-c": {
                "id": "contract-c",
                "inherits_from": "contract-a",  # Creates cycle!
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-c
version: 1.0.0
name: contract-c
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
        }

        validator = InheritanceValidator()
        result = validator.detect_circular_dependencies(
            contract_id="contract-a",
            contracts=contracts,
        )

        assert result.has_cycle is True
        assert result.cycle_path is not None
        assert len(result.cycle_path) >= 3
        # Cycle should include all three contracts
        assert "contract-a" in result.cycle_path
        assert "contract-b" in result.cycle_path
        assert "contract-c" in result.cycle_path

    @pytest.mark.requirement("3C-FR-011")
    def test_no_cycle_in_valid_chain(self) -> None:
        """Test that valid inheritance chain (no cycle) passes.

        Enterprise -> Domain -> Product (no cycles)

        Expected: No cycle detected
        """
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        contracts = {
            "enterprise": {
                "id": "enterprise",
                "inherits_from": None,  # Root contract
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: enterprise
version: 1.0.0
name: enterprise
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
            "domain": {
                "id": "domain",
                "inherits_from": "enterprise",
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: domain
version: 1.0.0
name: domain
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
            "product": {
                "id": "product",
                "inherits_from": "domain",
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: product
version: 1.0.0
name: product
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
        }

        validator = InheritanceValidator()
        result = validator.detect_circular_dependencies(
            contract_id="product",
            contracts=contracts,
        )

        assert result.has_cycle is False
        assert result.cycle_path is None

    @pytest.mark.requirement("3C-FR-011")
    def test_self_reference_detected(self) -> None:
        """Test that self-reference (A -> A) is detected.

        Contract A inherits from itself

        Expected: FLOE-E512 error
        """
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        contracts = {
            "contract-a": {
                "id": "contract-a",
                "inherits_from": "contract-a",  # Self-reference!
                "yaml": """
apiVersion: v3.1.0
kind: DataContract
id: contract-a
version: 1.0.0
name: contract-a
status: active
schema:
  - name: data
    properties:
      - name: id
        logicalType: string
""",
            },
        }

        validator = InheritanceValidator()
        result = validator.detect_circular_dependencies(
            contract_id="contract-a",
            contracts=contracts,
        )

        assert result.has_cycle is True
        assert result.cycle_path is not None
        assert "contract-a" in result.cycle_path

    @pytest.mark.requirement("3C-FR-011")
    def test_cycle_violation_returned_with_path(self) -> None:
        """Test that circular dependency creates FLOE-E512 violation with cycle path."""
        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        contracts = {
            "contract-a": {
                "id": "contract-a",
                "inherits_from": "contract-b",
                "yaml": "...",
            },
            "contract-b": {
                "id": "contract-b",
                "inherits_from": "contract-a",
                "yaml": "...",
            },
        }

        validator = InheritanceValidator()
        result = validator.detect_circular_dependencies(
            contract_id="contract-a",
            contracts=contracts,
        )

        # Convert to violation
        if result.has_cycle:
            violation = validator.cycle_to_violation(result)
            assert violation.error_code == "FLOE-E512"
            assert "circular" in violation.message.lower()
            assert "contract-a" in violation.message
            assert "contract-b" in violation.message


__all__ = [
    "TestSLAWeakeningDetection",
    "TestClassificationWeakeningDetection",
    "TestThreeTierInheritance",
    "TestContractValidatorInheritanceIntegration",
    "TestCircularDependencyDetection",
]
