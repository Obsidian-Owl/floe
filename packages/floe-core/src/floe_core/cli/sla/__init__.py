"""SLA compliance reporting CLI commands.

This module provides the `floe sla` command group for generating SLA compliance
reports from contract monitoring data (Epic 3D).

Commands:
    floe sla report: Generate compliance report for a contract over a time window

Example:
    $ floe sla report --contract orders_v1 --window weekly --format table
    $ floe sla report --format json

See Also:
    - specs/3d-contract-monitoring/spec.md: Contract monitoring specification
    - FR-039: CLI command for SLA reporting
"""

from __future__ import annotations

from floe_core.cli.sla.report import report

__all__: list[str] = ["report"]
