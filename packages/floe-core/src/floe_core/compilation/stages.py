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

import re
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import structlog

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.telemetry.tracing import create_span

if TYPE_CHECKING:
    from floe_core.enforcement.result import EnforcementResult
    from floe_core.schemas.compiled_artifacts import (
        CompiledArtifacts,
        ResolvedGovernance,
    )
    from floe_core.schemas.manifest import GovernanceConfig, PlatformManifest

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


def _discover_plugins_for_audit() -> list[tuple[PluginType, PluginMetadata]]:
    """Discover all registered plugins via entry points for audit.

    Loads each entry point, instantiates the plugin class (no-args), and
    returns a list of (PluginType, PluginMetadata) tuples suitable for
    ``verify_plugin_instrumentation()``.

    Plugins that fail to load or instantiate are logged and skipped.

    Returns:
        List of (PluginType, PluginMetadata) tuples for all discoverable plugins.
    """
    from importlib.metadata import entry_points

    results: list[tuple[PluginType, PluginMetadata]] = []

    for plugin_type in PluginType:
        try:
            eps = entry_points(group=plugin_type.value)
        except Exception as exc:
            logger.debug(
                "audit_entry_point_group_failed",
                plugin_type=plugin_type.name,
                error=str(exc),
            )
            continue

        for ep in eps:
            try:
                plugin_class = ep.load()
                instance = plugin_class()
                results.append((plugin_type, instance))
            except Exception as exc:
                logger.debug(
                    "audit_plugin_load_failed",
                    plugin_name=ep.name,
                    plugin_type=plugin_type.name,
                    error=str(exc),
                )

    return results


def _resolve_governance(
    manifest_governance: GovernanceConfig | None,
    resolved_cls: type[ResolvedGovernance],
    log: structlog.stdlib.BoundLogger,
) -> ResolvedGovernance | None:
    """Convert manifest GovernanceConfig to ResolvedGovernance for artifacts.

    Extracted from the ENFORCE stage to keep that block focused on
    enforcement logic. Emits a structlog event when lifecycle fields
    are present.

    Args:
        manifest_governance: GovernanceConfig from the parsed manifest, or None.
        resolved_cls: The ResolvedGovernance class (passed to avoid
            top-level import of compiled_artifacts).
        log: Bound structlog logger for the current compilation run.

    Returns:
        A ResolvedGovernance instance, or None if manifest_governance is None.
    """
    if manifest_governance is None:
        return None

    resolved = resolved_cls(
        pii_encryption=manifest_governance.pii_encryption,
        audit_logging=manifest_governance.audit_logging,
        policy_enforcement_level=manifest_governance.policy_enforcement_level,
        data_retention_days=manifest_governance.data_retention_days,
        default_ttl_hours=manifest_governance.default_ttl_hours,
        snapshot_keep_last=manifest_governance.snapshot_keep_last,
    )

    if resolved.default_ttl_hours is not None or resolved.snapshot_keep_last is not None:
        log.info(
            "governance_lifecycle_fields_resolved",
            default_ttl_hours=resolved.default_ttl_hours,
            snapshot_keep_last=resolved.snapshot_keep_last,
        )

    return resolved


def _build_lineage_config(manifest: PlatformManifest) -> dict[str, Any] | None:
    """Build lineage transport config from manifest observability settings.

    Args:
        manifest: Loaded PlatformManifest instance.

    Returns:
        Transport config dict if lineage is enabled, or None for NoOp emitter.
    """
    if manifest.observability is None:
        return None
    lineage = manifest.observability.lineage
    if not lineage.enabled:
        return None
    # HTTP transport requires an endpoint URL; without it, fall back to NoOp
    if lineage.transport == "http" and lineage.endpoint is None:
        return None
    config: dict[str, Any] = {"type": lineage.transport}
    if lineage.endpoint is not None:
        config["url"] = lineage.endpoint
    return config


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
    from floe_core.lineage.emitter import create_sync_emitter
    from floe_core.lineage.facets import TraceCorrelationFacetBuilder

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

        # Construct lineage emitter from manifest config (after LOAD, inside pipeline span
        # so TraceCorrelationFacetBuilder can capture the active OTel span context)
        try:
            _lineage_config = _build_lineage_config(manifest)
            emitter = create_sync_emitter(
                _lineage_config, default_namespace="floe.compilation"
            )
        except Exception as _build_err:
            # CWE-532: log type name only — exc_info may contain credential-bearing URLs
            log.warning("lineage_emitter_build_failed", error=type(_build_err).__name__)
            emitter = create_sync_emitter(None, default_namespace="floe.compilation")

        run_id: UUID | None = None
        try:
            run_facets: dict[str, Any] = {}
            trace_facet = TraceCorrelationFacetBuilder.from_otel_context()
            if trace_facet is not None:
                run_facets["traceCorrelation"] = trace_facet
            run_id = emitter.emit_start(job_name=spec.metadata.name, run_facets=run_facets)
        except Exception as _start_err:
            # CWE-532: log type name only — exc_info may contain credential-bearing URLs
            log.warning("lineage_emit_start_failed", error=type(_start_err).__name__)

        try:
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
                # Validate sink destinations against enterprise whitelist
                if manifest.approved_sinks is not None and spec.destinations is not None:
                    from floe_core.schemas.plugins import validate_sink_whitelist

                    for destination in spec.destinations:
                        validate_sink_whitelist(
                            sink_type=destination.sink_type,
                            approved_sinks=manifest.approved_sinks,
                        )
                    log.info(
                        "sink_whitelist_validated",
                        destination_count=len(spec.destinations),
                        approved_sinks=manifest.approved_sinks,
                    )

                # Plugin instrumentation audit (FR-016, FR-017)
                from floe_core.telemetry.audit import verify_plugin_instrumentation

                _audit_plugins = _discover_plugins_for_audit()
                _audit_warnings = verify_plugin_instrumentation(_audit_plugins)
                for _warn_msg in _audit_warnings:
                    log.warning("uninstrumented_plugin", message=_warn_msg)

                # Build pre-manifest enforcement summary from spec-level checks
                # Full post-dbt enforcement uses run_enforce_stage() separately
                from floe_core.schemas.compiled_artifacts import (
                    EnforcementResultSummary,
                    ResolvedGovernance,
                )

                # Enforcement level precedence: "stricter wins"
                # Strength ordering: off < warn < strict
                # Manifest is authoritative; spec can only strengthen (never weaken)
                _ENFORCEMENT_STRENGTH: dict[str, int] = {"off": 0, "warn": 1, "strict": 2}

                manifest_level: Literal["off", "warn", "strict"] | None = None
                if manifest.governance is not None:
                    manifest_level = manifest.governance.policy_enforcement_level

                spec_governance = getattr(spec, "governance", None)
                spec_level: Literal["off", "warn", "strict"] | None = None
                if spec_governance is not None:
                    raw_level = getattr(spec_governance, "enforcement_level", None)
                    if raw_level in ("off", "warn", "strict"):
                        spec_level = raw_level

                # Start with default "warn"
                enforcement_level: Literal["off", "warn", "strict"] = "warn"

                # Apply "stricter wins" merge
                if manifest_level is not None and spec_level is not None:
                    # Both present — pick the stricter one
                    spec_strength = _ENFORCEMENT_STRENGTH.get(spec_level, 1)
                    manifest_strength = _ENFORCEMENT_STRENGTH.get(manifest_level, 1)
                    if spec_strength >= manifest_strength:
                        enforcement_level = spec_level
                    else:
                        enforcement_level = manifest_level
                elif manifest_level is not None:
                    enforcement_level = manifest_level
                elif spec_level is not None:
                    enforcement_level = spec_level
                # else: both None, keep default "warn"

                policy_types_checked: list[str] = ["plugin_instrumentation"]
                if manifest.approved_sinks is not None and spec.destinations is not None:
                    policy_types_checked.append("sink_whitelist")

                enforcement_result = EnforcementResultSummary(
                    passed=True,
                    error_count=0,
                    warning_count=len(_audit_warnings),
                    policy_types_checked=policy_types_checked,
                    models_validated=0,
                    enforcement_level=enforcement_level,
                )

                resolved_governance = _resolve_governance(
                    manifest.governance,
                    ResolvedGovernance,
                    log,
                )

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

            # Post-COMPILE enforcement: validate models from resolved transforms
            # Only runs when governance config is present in the manifest
            if manifest.governance is not None:
                synthetic_dbt_manifest: dict[str, Any] = {"nodes": {}}
                for model in transforms.models:
                    node_key = f"model.floe.{model.name}"
                    synthetic_dbt_manifest["nodes"][node_key] = {
                        "name": model.name,
                        "resource_type": "model",
                        "tags": list(model.tags) if model.tags else [],
                        "depends_on": {
                            "nodes": [f"model.floe.{d}" for d in (model.depends_on or [])]
                        },
                        "description": "",
                        "columns": {},
                    }

                enforce_result = run_enforce_stage(
                    governance_config=manifest.governance,
                    dbt_manifest=synthetic_dbt_manifest,
                    dry_run=dry_run,
                )

                from floe_core.enforcement.result import create_enforcement_summary

                post_summary = create_enforcement_summary(enforce_result)

                merged_policy_types = sorted(
                    set(enforcement_result.policy_types_checked)
                    | set(post_summary.policy_types_checked)
                )
                enforcement_result = EnforcementResultSummary(
                    passed=enforcement_result.passed and post_summary.passed,
                    error_count=enforcement_result.error_count + post_summary.error_count,
                    warning_count=enforcement_result.warning_count + post_summary.warning_count,
                    policy_types_checked=merged_policy_types,
                    models_validated=post_summary.models_validated,
                    enforcement_level=enforcement_result.enforcement_level,
                    secrets_scanned=post_summary.secrets_scanned,
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
                    enforcement_result=enforcement_result,
                    quality_config=quality_config,
                    governance=resolved_governance,
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

            # Emit lineage COMPLETE event (non-blocking)
            try:
                if run_id is not None:
                    emitter.emit_complete(run_id, spec.metadata.name)
            except Exception as _complete_err:
                # CWE-532: log type name only — exc_info may contain credential-bearing URLs
                log.warning("lineage_emit_complete_failed", error=type(_complete_err).__name__)

        except Exception as _exc:
            # Emit lineage FAIL event only when run_id is available (non-blocking)
            if run_id is not None:
                try:
                    emitter.emit_fail(
                        run_id,
                        spec.metadata.name,
                        error_message=type(_exc).__name__,
                    )
                except Exception as _fail_err:
                    # CWE-532: log type name only — exc_info may contain credential-bearing URLs
                    log.warning("lineage_emit_fail_failed", error=type(_fail_err).__name__)
            raise
        finally:
            try:
                emitter.close()
            except Exception as _close_err:
                # CWE-532: log type name only — exc_info may contain credential-bearing URLs
                log.warning("lineage_emitter_close_failed", error=type(_close_err).__name__)

    return artifacts


def run_enforce_stage(
    governance_config: GovernanceConfig | None,
    dbt_manifest: dict[str, Any],
    *,
    dry_run: bool = False,
    token: str | None = None,
    principal: str | None = None,
    identity_plugin: Any = None,
    project_dir: Path | None = None,
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
        token: Authentication token for RBAC checks.
        principal: Principal identifier for RBAC checks.
        identity_plugin: Identity plugin for RBAC checks.
        project_dir: Project directory for secret scanning.

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
    from floe_core.enforcement.errors import PolicyEnforcementError

    # Validate optional string parameters
    if token is not None:
        if not token.strip():
            raise ValueError("token must be non-empty when provided")
        if len(token) > 2_048:
            raise ValueError("token exceeds maximum length")
        if not re.match(r"^[A-Za-z0-9._\-]+$", token):
            raise ValueError("token contains invalid characters")
    if principal is not None:
        if not principal.strip():
            raise ValueError("principal must be non-empty when provided")
        if len(principal) > 1_000:
            raise ValueError("principal exceeds maximum length")
        if not re.match(r"^[A-Za-z0-9@._\-]+$", principal):
            raise ValueError("principal contains invalid characters")

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
        "compile.enforce_post_compile",
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

        # Create GovernanceIntegrator and run all governance checks
        from floe_core.governance.integrator import GovernanceIntegrator

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=identity_plugin,
        )
        result = integrator.run_checks(
            project_dir=project_dir or Path.cwd(),
            token=token,
            principal=principal,
            dry_run=dry_run,
            enforcement_level=enforcement_level,
            dbt_manifest=dbt_manifest,
        )

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
