# Multi-arch Cube Store image for floe platform
#
# The upstream cubejs/cubestore image is AMD64-only. This Dockerfile
# enables multi-arch builds via docker buildx + QEMU emulation,
# producing a manifest that supports both linux/amd64 and linux/arm64.
#
# Build locally:
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     --push -t ghcr.io/obsidian-owl/cube-store:0.36.0 \
#     docker/cube-store/
#
# The nightly CI workflow builds and pushes automatically.

ARG CUBESTORE_VERSION=v0.36.0
FROM cubejs/cubestore:${CUBESTORE_VERSION}

LABEL org.opencontainers.image.title="cube-store"
LABEL org.opencontainers.image.description="Multi-arch Cube Store for floe platform testing"
LABEL org.opencontainers.image.source="https://github.com/obsidian-owl/floe"
