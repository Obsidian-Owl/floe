"""Compilation stages for the floe compilation pipeline.

The compilation pipeline consists of 6 sequential stages that transform
FloeSpec + PlatformManifest into CompiledArtifacts.

Stages:
    1. LOAD: Parse YAML files into Pydantic models
    2. VALIDATE: Schema validation and constraint checking
    3. RESOLVE: Plugin resolution and inheritance merging
    4. ENFORCE: Policy enforcement and governance checks
    5. COMPILE: Transform compilation and dbt profile generation
    6. GENERATE: Output CompiledArtifacts JSON

Each stage can produce errors that are tagged with the stage for debugging.

See Also:
    - specs/2b-compilation-pipeline/spec.md: Pipeline specification
    - ADR-0012: CompiledArtifacts contract
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import structlog

from floe_core.telemetry.tracing import create_span

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts
    from floe_core.schemas.manifest import GovernanceConfig

logger = structlog.get_logger(__name__)


class CompilationStage(str, Enum):
    """Stage in the compilation pipeline.

    Each stage processes input from the previous stage and either
    succeeds (passing data forward) or fails with a CompilationError.

    Attributes:
        LOAD: Parse YAML files into Pydantic models
        VALIDATE: Schema validation and constraint checking
        RESOLVE: Plugin resolution and inheritance merging
        ENFORCE: Policy enforcement and governance checks
        COMPILE: Transform compilation and dbt profile generation
        GENERATE: Output CompiledArtifacts JSON

    Example:
        >>> stage = CompilationStage.VALIDATE
        >>> stage.value
        'VALIDATE'
        >>> stage.exit_code
        1

    See Also:
        - CompilationError: Uses stage for error categorization
    """

    LOAD = "LOAD"
    """Parse YAML files (floe.yaml, manifest.yaml) into Pydantic models."""

    VALIDATE = "VALIDATE"
    """Schema validation and constraint checking (C001-C010)."""

    RESOLVE = "RESOLVE"
    """Plugin resolution and manifest inheritance merging."""

    ENFORCE = "ENFORCE"
    """Policy enforcement and governance checks."""

    COMPILE = "COMPILE"
    """Transform compilation and dbt profile generation."""

    GENERATE = "GENERATE"
    """Output CompiledArtifacts JSON to target directory."""

    @property
    def exit_code(self) -> int:
        """Get the CLI exit code for errors in this stage.

        Returns:
            1 for validation-related stages (LOAD, VALIDATE)
            2 for compilation-related stages (RESOLVE, ENFORCE, COMPILE, GENERATE)

        Example:
            >>> CompilationStage.VALIDATE.exit_code
            1
            >>> CompilationStage.COMPILE.exit_code
            2
        """
        # Exit code 1: Validation errors (input problems)
        # Exit code 2: Compilation errors (processing problems)
        validation_stages = {CompilationStage.LOAD, CompilationStage.VALIDATE}
        return 1 if self in validation_stages else 2

    @property
    def description(self) -> str:
        """Get human-readable description of this stage.

        Returns:
            Description of what the stage does.

        Example:
            >>> CompilationStage.LOAD.description
            'Parse YAML files into Pydantic models'
        """
        descriptions = {
            CompilationStage.LOAD: "Parse YAML files into Pydantic models",
            CompilationStage.VALIDATE: "Schema validation and constraint checking",
            CompilationStage.RESOLVE: "Plugin resolution and inheritance merging",
            CompilationStage.ENFORCE: "Policy enforcement and governance checks",
            CompilationStage.COMPILE: "Transform compilation and dbt profile generation",
            CompilationStage.GENERATE: "Output CompiledArtifacts JSON",
        }
        return descriptions[self]


def compile_pipeline(
    spec_path: Path,
    manifest_path: Path,
    *,
    dry_run: bool = False,
) -> CompiledArtifacts:
    """Execute the 6-stage compilation pipeline.

    Transforms FloeSpec + PlatformManifest into CompiledArtifacts through:
    1. LOAD: Parse YAML files
    2. VALIDATE: Schema validation (done during LOAD via Pydantic)
    3. RESOLVE: Plugin and manifest inheritance resolution
    4. ENFORCE: Policy enforcement (placeholder for governance)
    5. COMPILE: Transform compilation and dbt profile generation
    6. GENERATE: Build final CompiledArtifacts

    Each stage is wrapped in an OpenTelemetry span for observability (FR-013).

    Task: T080
    Requirements: FR-002 (Pipeline integration), US7 (Dry-run mode)

    Args:
        spec_path: Path to floe.yaml file.
        manifest_path: Path to manifest.yaml file.
        dry_run: If True, violations are reported but don't block compilation.

    Returns:
        CompiledArtifacts ready for serialization.

    Raises:
        CompilationException: If any stage fails.

    Example:
        >>> artifacts = compile_pipeline(Path("floe.yaml"), Path("manifest.yaml"))
        >>> artifacts.version
        '0.2.0'
    """
    # Local imports to avoid circular dependency (stages <- errors <- loader <- stages)
    from floe_core.compilation.builder import build_artifacts
    from floe_core.compilation.dbt_profiles import generate_dbt_profiles
    from floe_core.compilation.loader import load_floe_spec, load_manifest
    from floe_core.compilation.resolver import (
        resolve_manifest_inheritance,
        resolve_plugins,
        resolve_transform_compute,
    )

    log = logger.bind(spec_path=str(spec_path), manifest_path=str(manifest_path))

    # Track total compilation time
    pipeline_start = time.perf_counter()

    # Parent span for entire compilation pipeline
    with create_span(
        "compile.pipeline",
        attributes={
            "compile.spec_path": str(spec_path),
            "compile.manifest_path": str(manifest_path),
        },
    ) as pipeline_span:
        # Stage 1: LOAD - Parse YAML files
        stage_start = time.perf_counter()
        with create_span(
            "compile.load",
            attributes={"compile.stage": CompilationStage.LOAD.value},
        ):
            log.info("compilation_stage_start", stage=CompilationStage.LOAD.value)
            spec = load_floe_spec(spec_path)
            manifest = load_manifest(manifest_path)
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.LOAD.value,
                product_name=spec.metadata.name,
                duration_ms=round(duration_ms, 2),
            )

        # Stage 2: VALIDATE - Schema validation and quality provider validation
        stage_start = time.perf_counter()
        with create_span(
            "compile.validate",
            attributes={"compile.stage": CompilationStage.VALIDATE.value},
        ):
            log.info("compilation_stage_start", stage=CompilationStage.VALIDATE.value)
            if manifest.plugins.quality is not None:
                from floe_core.validation.quality_validation import (
                    validate_quality_provider,
                )

                validate_quality_provider(manifest.plugins.quality.provider)
                log.debug(
                    "quality_provider_validated",
                    provider=manifest.plugins.quality.provider,
                )
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.VALIDATE.value,
                duration_ms=round(duration_ms, 2),
            )

        # Stage 3: RESOLVE - Plugin and manifest inheritance resolution
        stage_start = time.perf_counter()
        with create_span(
            "compile.resolve",
            attributes={"compile.stage": CompilationStage.RESOLVE.value},
        ) as resolve_span:
            log.info("compilation_stage_start", stage=CompilationStage.RESOLVE.value)
            resolved_manifest = resolve_manifest_inheritance(manifest)
            plugins = resolve_plugins(resolved_manifest)
            transforms = resolve_transform_compute(spec, resolved_manifest)
            # Add resolution details as span attributes
            resolve_span.set_attribute("compile.compute_plugin", plugins.compute.type)
            resolve_span.set_attribute("compile.orchestrator_plugin", plugins.orchestrator.type)
            resolve_span.set_attribute("compile.model_count", len(transforms.models))
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.RESOLVE.value,
                compute_plugin=plugins.compute.type,
                orchestrator_plugin=plugins.orchestrator.type,
                model_count=len(transforms.models),
                duration_ms=round(duration_ms, 2),
            )

        # Stage 4: ENFORCE - Policy enforcement
        stage_start = time.perf_counter()
        with create_span(
            "compile.enforce",
            attributes={
                "compile.stage": CompilationStage.ENFORCE.value,
                "enforcement.dry_run": dry_run,
            },
        ):
            log.info(
                "compilation_stage_start",
                stage=CompilationStage.ENFORCE.value,
                dry_run=dry_run,
            )
            # Placeholder: Full enforcement requires dbt manifest.json which is
            # generated later by dbt compile. The run_enforce_stage() function
            # is used directly after dbt compilation for policy enforcement.
            # See: packages/floe-core/tests/integration/enforcement/ for usage
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.ENFORCE.value,
                dry_run=dry_run,
                duration_ms=round(duration_ms, 2),
            )

        # Stage 5: COMPILE - Transform compilation and dbt profile generation
        stage_start = time.perf_counter()
        with create_span(
            "compile.compile",
            attributes={"compile.stage": CompilationStage.COMPILE.value},
        ) as compile_span:
            log.info("compilation_stage_start", stage=CompilationStage.COMPILE.value)
            # Generate dbt profiles using compute plugin
            dbt_profiles = generate_dbt_profiles(
                plugins=plugins,
                product_name=spec.metadata.name,
            )
            compile_span.set_attribute("compile.profile_name", spec.metadata.name)
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.COMPILE.value,
                profile_name=spec.metadata.name,
                duration_ms=round(duration_ms, 2),
            )

        # Stage 6: GENERATE - Build final CompiledArtifacts
        stage_start = time.perf_counter()
        with create_span(
            "compile.generate",
            attributes={"compile.stage": CompilationStage.GENERATE.value},
        ) as generate_span:
            log.info("compilation_stage_start", stage=CompilationStage.GENERATE.value)
            quality_config = resolved_manifest.plugins.quality
            artifacts = build_artifacts(
                spec=spec,
                manifest=resolved_manifest,
                plugins=plugins,
                transforms=transforms,
                dbt_profiles=dbt_profiles,
                spec_path=spec_path,
                manifest_path=manifest_path,
                quality_config=quality_config,
            )
            generate_span.set_attribute("compile.artifacts_version", artifacts.version)
            duration_ms = (time.perf_counter() - stage_start) * 1000
            log.info(
                "compilation_stage_complete",
                stage=CompilationStage.GENERATE.value,
                version=artifacts.version,
                duration_ms=round(duration_ms, 2),
            )

        # Set final attributes on parent span
        pipeline_span.set_attribute("compile.product_name", spec.metadata.name)
        pipeline_span.set_attribute("compile.artifacts_version", artifacts.version)

        # Log total compilation time
        total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
        pipeline_span.set_attribute("compile.total_duration_ms", round(total_duration_ms, 2))
        log.info(
            "compilation_complete",
            product_name=spec.metadata.name,
            version=artifacts.version,
            total_duration_ms=round(total_duration_ms, 2),
        )

        return artifacts


def run_enforce_stage(
    governance_config: GovernanceConfig | None,
    dbt_manifest: dict[str, Any],
    *,
    dry_run: bool = False,
) -> EnforcementResult:
    """Run the ENFORCE stage of the compilation pipeline.

    Executes policy enforcement against a dbt manifest using the configured
    governance rules. This stage validates naming conventions, test coverage,
    and documentation requirements.

    Task: T074, T075, T076
    Requirements: FR-002 (Pipeline integration), US1 (Compile-time enforcement)

    Args:
        governance_config: The governance configuration from manifest.yaml.
            If None or policy_enforcement_level is 'off', enforcement is skipped.
        dbt_manifest: The compiled dbt manifest.json as a dictionary.
        dry_run: If True, violations are reported but don't block compilation.

    Returns:
        EnforcementResult containing pass/fail status and all violations.

    Raises:
        PolicyEnforcementError: If enforcement_level is 'strict' and there
            are error-severity violations (unless dry_run=True).

    Example:
        >>> config = GovernanceConfig(policy_enforcement_level="warn")
        >>> result = run_enforce_stage(config, manifest, dry_run=False)
        >>> result.passed
        True
    """
    # Local imports to avoid circular dependency
    from floe_core.enforcement import PolicyEnforcer
    from floe_core.enforcement.errors import PolicyEnforcementError

    log = logger.bind(
        component="run_enforce_stage",
        dry_run=dry_run,
    )

    start_time = time.perf_counter()

    # Skip enforcement if no governance config
    if governance_config is None:
        log.info("enforcement_skipped", reason="no_governance_config")
        return _create_skipped_result(enforcement_level="off")

    # Get enforcement level
    enforcement_level = governance_config.policy_enforcement_level or "warn"

    # Skip enforcement if level is 'off'
    if enforcement_level == "off":
        log.info("enforcement_skipped", reason="enforcement_level_off")
        return _create_skipped_result(enforcement_level="off")

    log = log.bind(enforcement_level=enforcement_level)

    # Run policy enforcement with OTel span
    with create_span(
        "compile.enforce",
        attributes={
            "compile.stage": CompilationStage.ENFORCE.value,
            "enforcement.level": enforcement_level,
            "enforcement.dry_run": dry_run,
        },
    ) as enforce_span:
        log.info(
            "enforcement_started",
            model_count=len(dbt_manifest.get("nodes", {})),
        )

        # Create PolicyEnforcer and run enforcement
        enforcer = PolicyEnforcer(governance_config=governance_config)
        result = enforcer.enforce(dbt_manifest, dry_run=dry_run)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Set OTel span attributes (T076)
        enforce_span.set_attribute("enforcement.passed", result.passed)
        enforce_span.set_attribute("enforcement.violation_count", len(result.violations))
        enforce_span.set_attribute("enforcement.error_count", result.error_count)
        enforce_span.set_attribute("enforcement.warning_count", result.warning_count)
        enforce_span.set_attribute("enforcement.duration_ms", round(duration_ms, 2))

        # Log enforcement result
        if result.violations:
            for violation in result.violations:
                log.warning(
                    "policy_violation",
                    error_code=violation.error_code,
                    policy_type=violation.policy_type,
                    model_name=violation.model_name,
                    message=violation.message,
                    severity=violation.severity,
                )

        log.info(
            "enforcement_completed",
            passed=result.passed,
            violation_count=len(result.violations),
            error_count=result.error_count,
            warning_count=result.warning_count,
            duration_ms=round(duration_ms, 2),
        )

        # Handle strict mode blocking (T075)
        # In strict mode, raise if there are error-severity violations
        # UNLESS dry_run is True (dry-run never raises)
        if enforcement_level == "strict" and not dry_run and result.error_count > 0:
            log.error(
                "enforcement_failed",
                reason="strict_mode_violations",
                error_count=result.error_count,
            )
            raise PolicyEnforcementError(violations=result.violations)

        # In warn mode, violations are logged but don't block
        # The result.passed is adjusted by PolicyEnforcer based on dry_run
        return result


def _create_skipped_result(
    enforcement_level: Literal["off", "warn", "strict"],
) -> EnforcementResult:
    """Create an EnforcementResult for skipped enforcement.

    Args:
        enforcement_level: The enforcement level (typically 'off').

    Returns:
        EnforcementResult that passes with no violations.
    """
    from floe_core.enforcement.result import (
        EnforcementResult,
        EnforcementSummary,
    )

    return EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(
            total_models=0,
            models_validated=0,
            naming_violations=0,
            coverage_violations=0,
            documentation_violations=0,
            duration_ms=0.0,
        ),
        enforcement_level=enforcement_level,
        manifest_version="unknown",
        timestamp=datetime.now(timezone.utc),
    )


__all__ = ["CompilationStage", "compile_pipeline", "run_enforce_stage"]
