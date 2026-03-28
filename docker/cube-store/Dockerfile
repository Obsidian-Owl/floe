# Cube Store image for floe platform
#
# The upstream cubejs/cubestore image is AMD64-only (no ARM64 manifest).
# This Dockerfile rebuilds and pushes to GHCR for supply chain pinning.
#
# Build locally:
#   docker buildx build --platform linux/amd64 \
#     --push -t ghcr.io/obsidian-owl/cube-store:0.36.0 \
#     docker/cube-store/
#
# The weekly CI workflow builds and pushes automatically.

ARG CUBESTORE_VERSION=v0.36.0
# Pin digest for supply chain integrity. Update digest when bumping version:
#   docker buildx imagetools inspect cubejs/cubestore:<new-version> | head -5
FROM cubejs/cubestore:${CUBESTORE_VERSION}@sha256:6a817f6e3bdefd4ec21260e7d7b5b8a71f4fc78fdf15a9ea940947bc683d81a0

LABEL org.opencontainers.image.title="cube-store"
LABEL org.opencontainers.image.description="Cube Store for floe platform testing"
LABEL org.opencontainers.image.source="https://github.com/obsidian-owl/floe"
