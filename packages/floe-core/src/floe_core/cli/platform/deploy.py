"""Platform deploy command.

Deploy the floe platform to a Kubernetes cluster using Helm.
Generates environment-specific values from HelmValuesConfig and
plugin contributions, then executes helm upgrade --install.

Example:
    $ floe platform deploy --env test
    $ floe platform deploy --env dev --dry-run
    $ floe platform deploy --env staging --set dagster.replicas=3
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import click
import yaml

from floe_core.cli.utils import ExitCode, error_exit, info, success, warn
from floe_core.helm import HelmValuesConfig, HelmValuesGenerator
from floe_core.helm.parsing import parse_set_values


@click.command(
    name="deploy",
    help="Deploy platform to environment (FR-018).",
)
@click.option(
    "--env",
    "-e",
    type=click.Choice(["test", "dev", "staging", "prod"]),
    default="test",
    help="Target environment (default: test).",
)
@click.option(
    "--chart",
    "-c",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Path to Helm chart directory (default: charts/floe-platform).",
)
@click.option(
    "--namespace",
    "-n",
    type=str,
    default=None,
    help="K8s namespace (default: floe-{env}).",
)
@click.option(
    "--values",
    "-f",
    "values_files",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    multiple=True,
    help="Additional values files to merge. Can be repeated.",
)
@click.option(
    "--set",
    "set_values",
    multiple=True,
    help="Override values using key=value. Can be repeated.",
)
@click.option(
    "--release-name",
    type=str,
    default="floe-platform",
    help="Helm release name (default: floe-platform).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print helm command without executing.",
)
@click.option(
    "--timeout",
    type=str,
    default="10m",
    help="Helm timeout string (default: 10m).",
)
@click.option(
    "--skip-schema-validation",
    is_flag=True,
    default=True,
    help="Skip Helm schema validation (default: True due to Dagster subchart issues).",
)
def deploy_command(
    env: str,
    chart: Path | None,
    namespace: str | None,
    values_files: tuple[Path, ...],
    set_values: tuple[str, ...],
    release_name: str,
    dry_run: bool,
    timeout: str,
    skip_schema_validation: bool,
) -> None:
    """Deploy platform to target environment.

    Generates environment-specific Helm values using HelmValuesGenerator,
    merges plugin values and user overrides, then deploys using helm upgrade --install.

    Args:
        env: Target environment (test, dev, staging, prod)
        chart: Path to Helm chart directory
        namespace: Kubernetes namespace (default: floe-{env})
        values_files: Additional values files to merge
        set_values: Override values using key=value syntax
        release_name: Helm release name
        dry_run: If True, print command without executing
        timeout: Helm timeout string
        skip_schema_validation: If True, pass --skip-schema-validation to helm
    """
    # Resolve chart path
    chart_path = chart or Path("charts/floe-platform")
    if not chart_path.exists():
        error_exit(
            "Chart directory not found",
            exit_code=ExitCode.FILE_NOT_FOUND,
            path=str(chart_path),
        )

    # Compute namespace
    namespace = namespace or f"floe-{env}"

    # Create HelmValuesConfig with defaults
    info(f"Generating values for environment: {env}")
    config = HelmValuesConfig.with_defaults(environment=env)

    # Create generator
    generator = HelmValuesGenerator(config)

    # Load environment-specific values file if it exists
    env_values_path = chart_path / f"values-{env}.yaml"
    if env_values_path.exists():
        info(f"Loading environment values: {env_values_path.name}")
        try:
            with env_values_path.open() as f:
                env_values = yaml.safe_load(f)
                if env_values:
                    generator.add_plugin_values(env_values)
        except Exception as e:
            error_exit(
                f"Failed to load environment values file: {e}",
                exit_code=ExitCode.FILE_NOT_FOUND,
            )

    # Load additional values files
    for values_file in values_files:
        info(f"Loading additional values: {values_file.name}")
        try:
            with values_file.open() as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    generator.add_plugin_values(loaded)
        except Exception as e:
            error_exit(
                f"Failed to load values file {values_file}: {e}",
                exit_code=ExitCode.FILE_NOT_FOUND,
            )

    # Parse --set values
    user_overrides = parse_set_values(set_values, warn_fn=warn)
    if user_overrides:
        info(f"Applying {len(user_overrides)} user overrides")
        generator.set_user_overrides(user_overrides)

    # Generate final values
    values = generator.generate()

    # Write to temp file
    temp_file = None
    try:
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="floe-deploy-",
            delete=False,
        )
        yaml.safe_dump(values, temp_file, default_flow_style=False, sort_keys=False)
        temp_file.close()
        temp_values_path = Path(temp_file.name)

        # Build helm command
        helm_cmd = [
            "helm",
            "upgrade",
            "--install",
            release_name,
            str(chart_path),
            "-n",
            namespace,
            "--create-namespace",
            "-f",
            str(temp_values_path),
            "--wait",
            "--timeout",
            timeout,
        ]

        if skip_schema_validation:
            helm_cmd.append("--skip-schema-validation")

        # Dry-run: print command and exit
        if dry_run:
            info("Dry-run mode: helm command would be:")
            info(" ".join(helm_cmd))
            info("")
            info("Generated values content:")
            info("-" * 60)
            info(yaml.safe_dump(values, default_flow_style=False, sort_keys=False))
            info("-" * 60)
            success("Dry-run complete.")
            return

        # Execute helm command
        info(f"Deploying {release_name} to {namespace}...")
        info(f"Chart: {chart_path}")
        info(f"Timeout: {timeout}")

        try:
            result = subprocess.run(
                helm_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            success(f"Deployment successful: {release_name} in namespace {namespace}")
            if result.stdout:
                info(result.stdout)

        except subprocess.CalledProcessError as e:
            error_msg = "Helm deployment failed"
            if e.stderr:
                error_msg = f"{error_msg}\n{e.stderr}"
            error_exit(error_msg, exit_code=ExitCode.GENERAL_ERROR)

    finally:
        # Clean up temp file
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


__all__: list[str] = ["deploy_command"]
