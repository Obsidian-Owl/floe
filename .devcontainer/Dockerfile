FROM node:20

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# ============================================================
# System packages
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  nano \
  vim \
  # socat: required by docker-outside-of-docker feature's docker-init.sh
  # when host docker socket GID doesn't match container's docker group GID
  socat \
  # Python build dependencies
  python3-venv \
  python3-dev \
  build-essential \
  # Shell script linting (used by quality gates)
  shellcheck \
  # Network utilities for E2E test port checks
  netcat-openbsd \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist shell history (zsh).
RUN mkdir /commandhistory \
  && touch /commandhistory/.zsh_history \
  && chown -R $USERNAME /commandhistory

ENV DEVCONTAINER=true

# Create workspace and config directories.
# Also create /workspaces/<workspace-name> symlink that devpod expects:
# devpod's SSH server uses --workdir '/workspaces/<workspace-id>' regardless of
# the workspaceFolder config, so the path must exist in the container.
RUN mkdir -p /workspace /home/node/.claude /home/node/.kube /workspaces && \
  ln -s /workspace /workspaces/floe && \
  chown -R node:node /workspace /home/node/.claude /home/node/.kube /workspaces

WORKDIR /workspace

# ============================================================
# git-delta
# ============================================================
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

# ============================================================
# Kubernetes tooling (kubectl, kind, helm)
# ============================================================
ARG KUBECTL_VERSION=1.29.0
RUN ARCH=$(dpkg --print-architecture) && \
  curl -LO "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" && \
  chmod +x kubectl && mv kubectl /usr/local/bin/kubectl

ARG KIND_VERSION=0.22.0
RUN ARCH=$(dpkg --print-architecture) && \
  curl -Lo kind "https://kind.sigs.k8s.io/dl/v${KIND_VERSION}/kind-linux-${ARCH}" && \
  chmod +x kind && mv kind /usr/local/bin/kind

ARG HELM_VERSION=3.16.4
RUN ARCH=$(dpkg --print-architecture) && \
  curl -LO "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
  tar -xzf "helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
  mv "linux-${ARCH}/helm" /usr/local/bin/helm && \
  rm -rf "linux-${ARCH}" "helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz"

# ============================================================
# Sudoers — firewall + Docker socket init (passwordless)
# ============================================================
#
# The docker-outside-of-docker devcontainer feature mounts the host Docker
# socket at /var/run/docker-host.sock and runs /usr/local/share/docker-init.sh
# (via ENTRYPOINT) to make it accessible. That script calls `sudoIf` for:
#   groupmod  — to align container docker group GID with host socket GID
#   tee       — to write the socat log file
#   rm        — to remove the old docker.sock before socat creates a new one
#   socat     — to proxy /var/run/docker-host.sock to /var/run/docker.sock
#
# Two pitfalls that both cause "sudo: a terminal is required" failures:
#
# 1. FILE NAME COLLISION: The feature's install.sh writes /etc/sudoers.d/node-docker
#    during image build (after Dockerfile RUN layers), overwriting any file with that
#    exact name. Use "node-docker-init" to avoid the collision so our entries survive.
#
# 2. use_pty DEFAULT: The base node:20 image ships /etc/sudoers with "Defaults use_pty",
#    which requires a pseudo-TTY for all sudo invocations. docker-init.sh runs as the
#    container ENTRYPOINT without a TTY, so every sudoIf call fails with
#    "sudo: a terminal is required". Override with "!use_pty" for the node user.
COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh && \
  echo "node ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/node-firewall && \
  chmod 0440 /etc/sudoers.d/node-firewall && \
  printf '%s\n' \
    'Defaults:node !use_pty' \
    'node ALL=(root) NOPASSWD: /usr/bin/tee' \
    'node ALL=(root) NOPASSWD: /usr/sbin/groupmod' \
    'node ALL=(root) NOPASSWD: /bin/rm' \
    'node ALL=(root) NOPASSWD: /usr/bin/socat' \
    > /etc/sudoers.d/node-docker-init && \
  chmod 0440 /etc/sudoers.d/node-docker-init

# ============================================================
# Switch to non-root user
# ============================================================
USER node

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano

# ============================================================
# uv (Python package manager)
# ============================================================
ARG UV_VERSION=0.7.2
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
ENV PATH="/home/node/.local/bin:$PATH"

# ============================================================
# Zsh + Oh My Zsh
# ============================================================
ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
  -p git \
  -p fzf \
  -p kubectl \
  -p helm \
  -a "source /usr/share/doc/fzf/examples/key-bindings.zsh" \
  -a "source /usr/share/doc/fzf/examples/completion.zsh" \
  -a "export HISTFILE=/commandhistory/.zsh_history" \
  -a "export HISTSIZE=10000" \
  -a "export SAVEHIST=10000" \
  -a "setopt APPEND_HISTORY SHARE_HISTORY INC_APPEND_HISTORY HIST_IGNORE_DUPS" \
  -a 'export PATH="/home/node/.local/bin:$PATH"' \
  -x

# ============================================================
# Claude Code CLI
# ============================================================
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Set zsh as the default entry point for Warp Terminal connections
ENTRYPOINT ["/bin/zsh"]
