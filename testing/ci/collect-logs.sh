#!/bin/bash
# Collect K8s logs on test failure
# Used by both local testing and CI
#
# Usage: ./testing/ci/collect-logs.sh [namespace]
#
# Environment:
#   TEST_NAMESPACE    K8s namespace (default: floe-test)

set -euo pipefail

NAMESPACE="${1:-${TEST_NAMESPACE:-floe-test}}"

echo "=== Pod Status ===" >&2
kubectl get pods -n "${NAMESPACE}" -o wide 2>&1 || true

echo "" >&2
echo "=== Recent Events ===" >&2
kubectl get events -n "${NAMESPACE}" --sort-by='.lastTimestamp' 2>&1 | tail -20 || true

echo "" >&2
echo "=== Failed Pod Logs (last 30 lines) ===" >&2
for pod in $(kubectl get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running,status.phase!=Succeeded -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
    echo "--- ${pod} ---" >&2
    kubectl logs "${pod}" -n "${NAMESPACE}" --tail=30 2>&1 | grep -i "error\|fail\|exception" || true
done
