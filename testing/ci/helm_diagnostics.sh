#!/usr/bin/env bash
set -euo pipefail

RELEASE="${1:-floe-test}"
NAMESPACE="${2:-floe-test}"

section() {
  printf '\n==== %s ====\n' "$1"
}

section "Helm status"
helm status "$RELEASE" --namespace "$NAMESPACE" || true

section "Helm history"
helm history "$RELEASE" --namespace "$NAMESPACE" || true

section "Kubernetes objects"
kubectl get all -n "$NAMESPACE" -o wide || true

section "Recent events"
kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp || true

section "Pod descriptions"
kubectl describe pods -n "$NAMESPACE" || true

section "Helm test pod logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep test || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Polaris logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep polaris || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "MinIO logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep minio || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Dagster webserver logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep dagster-webserver || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Dagster daemon logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep dagster-daemon || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Marquez logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep marquez || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done
