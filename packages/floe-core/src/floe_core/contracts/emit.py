"""Emit generated contract bindings for shell and Helm consumers."""

from __future__ import annotations

import argparse
import shlex
from collections.abc import Sequence

from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    ComponentId,
    render_service_name,
    service_contract_by_name,
    test_runner_services,
)


def render_shell_defaults() -> str:
    """Render shell assignments for contract-owned defaults."""
    lines = [
        f"FLOE_DEFAULT_RELEASE_NAME={shlex.quote(DEFAULT_RELEASE_NAME)}",
        f"FLOE_DEFAULT_NAMESPACE={shlex.quote(DEFAULT_NAMESPACE)}",
        f"FLOE_DEFAULT_EXECUTION_CONTEXT={shlex.quote('host')}",
    ]
    return "\n".join(lines) + "\n"


def render_service_name_output(component_name: str, release_name: str) -> str:
    """Render a service name and trailing newline for shell command use."""
    service = service_contract_by_name(component_name)
    return render_service_name(service.component_id, release_name=release_name) + "\n"


def render_service_host_port_output(component_name: str) -> str:
    """Render a service host port and trailing newline for shell command use."""
    service = service_contract_by_name(component_name)
    return f"{service.host_port}\n"


def _helm_host_helper(component_id: ComponentId) -> str:
    helper_by_component = {
        ComponentId.POSTGRESQL: 'include "floe-platform.postgresql.host" $context',
        ComponentId.POLARIS: 'include "floe-platform.polaris.fullname" $context',
        ComponentId.POLARIS_MANAGEMENT: 'include "floe-platform.polaris.fullname" $context',
        ComponentId.MINIO: 'include "floe-platform.minio.fullname" $context',
        ComponentId.MINIO_CONSOLE: 'include "floe-platform.minio.fullname" $context',
        ComponentId.MARQUEZ: 'include "floe-platform.marquez.fullname" $context',
        ComponentId.DAGSTER_WEBSERVER: 'include "floe-platform.dagster.webserverName" $context',
        ComponentId.JAEGER_QUERY: 'include "floe-platform.jaeger.queryName" $context',
        ComponentId.OTEL_COLLECTOR_GRPC: 'include "floe-platform.otel.fullname" $context',
        ComponentId.OTEL_COLLECTOR_HTTP: 'include "floe-platform.otel.fullname" $context',
    }
    return helper_by_component[component_id]


def render_helm_test_env_template() -> str:
    """Render the Helm template helper consumed by the test-runner Job."""
    lines = [
        '{{- define "floe-platform.testRunner.contractEnv" -}}',
        "{{- $context := . -}}",
        "- name: FLOE_EXECUTION_CONTEXT",
        '  value: "in-cluster"',
        "- name: FLOE_RELEASE_NAME",
        "  value: {{ $context.Release.Name | quote }}",
        "- name: FLOE_NAMESPACE",
        "  value: {{ $context.Release.Namespace | quote }}",
    ]
    for service in test_runner_services():
        helper = _helm_host_helper(service.component_id)
        lines.extend(
            [
                f"- name: {service.host_env_var}",
                "  value: {{ " + helper + " | quote }}",
                f"- name: {service.port_env_var}",
                f'  value: "{service.default_port}"',
            ]
        )
    lines.append("{{- end -}}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Command entry point for contract binding emission."""
    parser = argparse.ArgumentParser(prog="python -m floe_core.contracts.emit")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("shell-defaults")

    service_parser = subcommands.add_parser("service-name")
    service_parser.add_argument("component")
    service_parser.add_argument("--release-name", default=DEFAULT_RELEASE_NAME)

    host_port_parser = subcommands.add_parser("service-host-port")
    host_port_parser.add_argument("component")

    subcommands.add_parser("helm-test-env")

    args = parser.parse_args(argv)
    if args.command == "shell-defaults":
        print(render_shell_defaults(), end="")
        return 0
    if args.command == "service-name":
        print(render_service_name_output(args.component, args.release_name), end="")
        return 0
    if args.command == "service-host-port":
        print(render_service_host_port_output(args.component), end="")
        return 0
    if args.command == "helm-test-env":
        print(render_helm_test_env_template(), end="")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
