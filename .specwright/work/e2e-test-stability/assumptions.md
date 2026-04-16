# Assumptions: E2E Test Stability — Round 2

## A1: Polaris test instance supports OAuth2 client credentials flow

- **Category**: integration
- **Status**: ACCEPTED
- **Evidence**: `testing/ci/polaris-auth.sh` uses `curl -u demo-admin:demo-secret`
  against `$polaris_url/api/catalog/v1/oauth/tokens` with `grant_type=client_credentials`.
  This is the standard Polaris REST catalog OAuth2 endpoint. The Helm chart deploys
  Polaris with these default credentials.
- **Impact if wrong**: Config validation passes but auth fails at runtime → same
  number of failures, different error message.

## A2: `:memory:` is the intended DuckDB target for demo profiles

- **Category**: behavioral
- **Status**: ACCEPTED
- **Evidence**: `tests/e2e/conftest.py:1132` explicitly generates profiles with
  `path: ":memory:"`. This was an intentional change — `:memory:` avoids needing
  a writable volume mount, which is simpler for container environments.
- **Impact if wrong**: The assertion relaxation would mask a profile compilation
  regression. Low risk since conftest explicitly sets this value.

## A3: Port 3100/5100/4317 are canonical port-forward targets

- **Category**: environmental
- **Status**: ACCEPTED
- **Evidence**: `scripts/devpod-tunnels.sh` lines 29-36 defines:
  `3100:dagster-webserver`, `5100:marquez-api`, `4317:otel-grpc`.
  These match the `make test-e2e` port-forward setup.
- **Impact if wrong**: Hook becomes a false-negative guardrail.

## A4: floe-iceberg has no conflicting transitive dependencies

- **Category**: technical
- **Status**: ACCEPTED
- **Evidence**: The Dockerfile runs `pip check` at build time (line ~132).
  Any dependency conflict would fail the Docker build, not cause a runtime issue.
  `floe-iceberg` dependencies (pyiceberg, pyarrow) are already transitive deps
  of the existing packages.
- **Impact if wrong**: Build fails — caught immediately, no runtime risk.
