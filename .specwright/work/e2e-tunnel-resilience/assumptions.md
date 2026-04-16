# Assumptions: E2E Tunnel Resilience

## A1: DevPod Uses System OpenSSH (not Go client)

**Type**: Technical/Clarify
**Status**: ACCEPTED (auto-resolved)
**Evidence**: macOS ships with OpenSSH. DevPod defaults to system SSH when available. The `devpod-tunnels.sh` script uses raw `ssh` (not `devpod ssh`), confirming system OpenSSH for service tunnels. The kubeconfig sync uses `devpod ssh` which also delegates to system SSH on macOS.
**Risk if wrong**: SSH keepalive options would be silently ignored. Mitigation: test empirically after implementation.

## A2: pytest-rerunfailures Compatible with Current pytest Stack

**Type**: Technical/Clarify
**Status**: ACCEPTED (auto-resolved)
**Evidence**: floe uses pytest 9.0.2. pytest-rerunfailures 16.1 requires pytest 8.0+. No known conflicts with pytest-timeout (4.2.0), pytest-asyncio (1.3.0), or pytest-cov (7.0.0). The 16.0 xdist incompatibility was fixed in 16.1.
**Risk if wrong**: Plugin conflict at import time. Mitigation: install and run unit tests to verify.

## A3: Port-Forward Watchdog Won't Cause Restart Storms

**Type**: Technical/Clarify
**Status**: ACCEPTED (auto-resolved)
**Evidence**: 30-second check interval with TCP-only probe. If the K8s API tunnel is dead, `kubectl port-forward` will fail immediately (not hang), and the watchdog will log the failure without looping. The check is `(echo >/dev/tcp/localhost/PORT) 2>/dev/null` which returns instantly.
**Risk if wrong**: Rapid process creation. Mitigation: add rate limiting (max 1 restart per port per 60 seconds).

## A4: ServiceEndpoint Resolves Same as Hardcoded localhost

**Type**: Technical/Clarify
**Status**: ACCEPTED (auto-resolved)
**Evidence**: `ServiceEndpoint("otel-collector")` resolves to `localhost:4317` when `INTEGRATION_TEST_HOST` is not set to `k8s`. `ServiceEndpoint("marquez")` resolves to `localhost:5100`. Both match current hardcoded values. Verified by reading `SERVICE_DEFAULT_PORTS` in `testing/fixtures/services.py`.
**Risk if wrong**: OTel/OpenLineage endpoints would resolve differently, breaking telemetry seeding. Mitigation: assert endpoint URL in a test.
