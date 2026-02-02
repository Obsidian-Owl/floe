"""Helm values generator for floe platform deployment.

This module provides the HelmValuesGenerator class that transforms
CompiledArtifacts into environment-specific Helm values files.

The generator combines:
1. Chart default values
2. Plugin-specific values from get_helm_values()
3. Environment-specific overrides (based on HelmValuesConfig)
4. User-provided values

Example:
    >>> from floe_core.helm.generator import HelmValuesGenerator
    >>> from floe_core.helm.schemas import HelmValuesConfig
    >>>
    >>> config = HelmValuesConfig.with_defaults(environment="staging")
    >>> generator = HelmValuesGenerator(config)
    >>> values = generator.generate()
    >>> generator.write_values("values-staging.yaml", values)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from floe_core.helm.merger import deep_merge, merge_all
from floe_core.helm.schemas import HelmValuesConfig

if TYPE_CHECKING:
    from collections.abc import Sequence


class SchemaValidationError(Exception):
    """Raised when generated values fail schema validation."""

    def __init__(
        self,
        message: str,
        errors: list[str] | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message
            errors: List of specific validation errors
        """
        super().__init__(message)
        self.errors = errors or []


class HelmValuesGenerator:
    """Generate Helm values from configuration and plugin values.

    This class is the main entry point for generating environment-specific
    Helm values. It combines multiple sources of configuration using
    deep merge semantics.

    Attributes:
        config: Helm values configuration including environment and presets
        base_values: Optional base values to start from (e.g., chart defaults)
        plugin_values: Optional list of plugin-contributed values

    Example:
        >>> config = HelmValuesConfig.with_defaults(environment="prod")
        >>> generator = HelmValuesGenerator(config)
        >>> generator.add_plugin_values({"polaris": {"enabled": True}})
        >>> values = generator.generate()
    """

    def __init__(
        self,
        config: HelmValuesConfig | None = None,
        *,
        base_values: dict[str, Any] | None = None,
        schema_path: Path | str | None = None,
    ) -> None:
        """Initialize the generator.

        Args:
            config: Helm values configuration. If None, uses dev defaults.
            base_values: Base values to merge into (e.g., chart defaults)
            schema_path: Optional path to JSON Schema for validation
        """
        self.config = config or HelmValuesConfig.with_defaults()
        self.base_values = base_values or {}
        self._plugin_values: list[dict[str, Any]] = []
        self._user_overrides: dict[str, Any] = {}
        self._schema_path = Path(schema_path) if schema_path else None
        self._schema: dict[str, Any] | None = None

    def add_plugin_values(self, values: dict[str, Any]) -> None:
        """Add plugin-contributed values.

        Plugin values are merged in order they are added.

        Args:
            values: Dictionary of Helm values from a plugin
        """
        self._plugin_values.append(values)

    def add_plugin_values_batch(self, values_list: Sequence[dict[str, Any]]) -> None:
        """Add multiple plugin values at once.

        Args:
            values_list: Sequence of value dictionaries
        """
        self._plugin_values.extend(values_list)

    def set_user_overrides(self, overrides: dict[str, Any]) -> None:
        """Set user-provided value overrides.

        User overrides take highest precedence and are applied last.

        Args:
            overrides: Dictionary of user-provided overrides
        """
        self._user_overrides = overrides

    def generate(self) -> dict[str, Any]:
        """Generate the final Helm values dictionary.

        Merges values in this order (later overrides earlier):
        1. Base values (chart defaults)
        2. Environment configuration
        3. Plugin values (in order added)
        4. User overrides

        Returns:
            Complete Helm values dictionary
        """
        # Start with base values
        result = dict(self.base_values)

        # Add environment configuration
        env_values = self.config.to_values_dict()
        result = deep_merge(result, env_values)

        # Merge plugin values
        if self._plugin_values:
            plugin_merged = merge_all(*self._plugin_values)
            result = deep_merge(result, plugin_merged)

        # Apply user overrides last
        if self._user_overrides:
            result = deep_merge(result, self._user_overrides)

        return result

    def generate_for_environments(
        self,
        environments: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        """Generate values for multiple environments.

        Creates separate values for each environment while preserving
        the current plugin values and user overrides.

        Args:
            environments: List of environment names (e.g., ["dev", "staging", "prod"])

        Returns:
            Dictionary mapping environment name to values dictionary
        """
        results: dict[str, dict[str, Any]] = {}

        for env in environments:
            env_config = HelmValuesConfig(
                environment=env,
                cluster_mapping=self.config.cluster_mapping,
                resource_presets=self.config.resource_presets,
                enable_autoscaling=env == "prod",
                enable_network_policies=env in ("staging", "prod"),
                enable_pod_disruption_budget=env == "prod",
            )
            env_generator = HelmValuesGenerator(
                config=env_config,
                base_values=self.base_values,
            )
            env_generator._plugin_values = list(self._plugin_values)
            env_generator._user_overrides = self._user_overrides.copy()

            results[env] = env_generator.generate()

        return results

    def write_values(
        self,
        output_path: Path | str,
        values: dict[str, Any] | None = None,
    ) -> Path:
        """Write values to a YAML file.

        Args:
            output_path: Path to write the values file
            values: Values to write. If None, generates values.

        Returns:
            Path to the written file
        """
        if values is None:
            values = self.generate()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            yaml.safe_dump(values, f, default_flow_style=False, sort_keys=False)

        return output_path

    def write_environment_values(
        self,
        output_dir: Path | str,
        environments: Sequence[str],
        *,
        filename_template: str = "values-{env}.yaml",
    ) -> list[Path]:
        """Write values files for multiple environments.

        Args:
            output_dir: Directory to write files to
            environments: List of environment names
            filename_template: Template for filenames, {env} is replaced

        Returns:
            List of paths to written files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        all_values = self.generate_for_environments(environments)
        written_paths: list[Path] = []

        for env, values in all_values.items():
            filename = filename_template.format(env=env)
            path = output_dir / filename
            self.write_values(path, values)
            written_paths.append(path)

        return written_paths

    def to_helm_set_args(self, values: dict[str, Any] | None = None) -> list[str]:
        """Convert values to --set arguments for helm CLI.

        Args:
            values: Values to convert. If None, generates values.

        Returns:
            List of --set arguments
        """
        from floe_core.helm.merger import flatten_dict

        if values is None:
            values = self.generate()

        flat = flatten_dict(values)
        args: list[str] = []

        for key, value in flat.items():
            if isinstance(value, bool):
                value_str = str(value).lower()
            elif isinstance(value, (int, float)):
                value_str = str(value)
            elif value is None:
                value_str = "null"
            else:
                value_str = str(value)

            args.append(f"--set={key}={value_str}")

        return args

    def load_schema(self, schema_path: Path | str | None = None) -> dict[str, Any]:
        """Load JSON Schema from file.

        Args:
            schema_path: Path to schema file. Uses constructor path if None.

        Returns:
            Parsed JSON Schema dictionary

        Raises:
            FileNotFoundError: If schema file does not exist
            ValueError: If schema is not valid JSON
        """
        path = Path(schema_path) if schema_path else self._schema_path
        if path is None:
            msg = "No schema path provided"
            raise ValueError(msg)

        if not path.exists():
            msg = f"Schema file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open() as f:
            schema: dict[str, Any] = json.load(f)
            self._schema = schema

        return schema

    def validate(
        self,
        values: dict[str, Any] | None = None,
        *,
        schema_path: Path | str | None = None,
    ) -> list[str]:
        """Validate values against JSON Schema.

        Args:
            values: Values to validate. If None, generates values.
            schema_path: Optional schema path override.

        Returns:
            List of validation error messages (empty if valid)

        Raises:
            SchemaValidationError: If validation fails and raise_on_error=True
            ValueError: If no schema available
        """
        try:
            import jsonschema
        except ImportError as e:
            msg = "jsonschema package required for validation"
            raise ImportError(msg) from e

        if values is None:
            values = self.generate()

        # Load schema if needed
        if schema_path:
            self.load_schema(schema_path)
        elif self._schema is None and self._schema_path:
            self.load_schema()

        if self._schema is None:
            msg = "No schema loaded for validation"
            raise ValueError(msg)

        errors: list[str] = []
        validator = jsonschema.Draft7Validator(self._schema)

        for error in validator.iter_errors(values):
            path = ".".join(str(p) for p in error.absolute_path)
            if path:
                errors.append(f"{path}: {error.message}")
            else:
                errors.append(error.message)

        return errors

    def generate_and_validate(
        self,
        *,
        schema_path: Path | str | None = None,
        raise_on_error: bool = True,
    ) -> tuple[dict[str, Any], list[str]]:
        """Generate values and validate against schema.

        Args:
            schema_path: Optional schema path override.
            raise_on_error: If True, raise SchemaValidationError on failure.

        Returns:
            Tuple of (values, errors). Errors empty if valid.

        Raises:
            SchemaValidationError: If validation fails and raise_on_error=True
        """
        values = self.generate()
        errors = self.validate(values, schema_path=schema_path)

        if errors and raise_on_error:
            raise SchemaValidationError(
                f"Generated values failed schema validation: {len(errors)} error(s)",
                errors=errors,
            )

        return values, errors


def generate_values_from_config(
    config: HelmValuesConfig,
    plugin_values: Sequence[dict[str, Any]] | None = None,
    user_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to generate values from configuration.

    Args:
        config: Helm values configuration
        plugin_values: Optional list of plugin-contributed values
        user_overrides: Optional user-provided overrides

    Returns:
        Complete Helm values dictionary
    """
    generator = HelmValuesGenerator(config)

    if plugin_values:
        generator.add_plugin_values_batch(plugin_values)

    if user_overrides:
        generator.set_user_overrides(user_overrides)

    return generator.generate()


__all__: list[str] = [
    "HelmValuesGenerator",
    "SchemaValidationError",
    "generate_values_from_config",
]
