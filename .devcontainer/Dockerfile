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
  # Python build dependencies
  python3-venv \
  python3-dev \
  build-essential \
  # Network utilities for E2E test port checks
  netcat-openbsd \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

ENV DEVCONTAINER=true

# Create workspace and config directories
RUN mkdir -p /workspace /home/node/.claude /home/node/.kube && \
  chown -R node:node /workspace /home/node/.claude /home/node/.kube

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

ARG HELM_VERSION=3.14.0
RUN ARCH=$(dpkg --print-architecture) && \
  curl -LO "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
  tar -xzf "helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
  mv "linux-${ARCH}/helm" /usr/local/bin/helm && \
  rm -rf "linux-${ARCH}" "helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz"

# ============================================================
# Sudoers — firewall + K8s tooling (passwordless)
# ============================================================
COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh && \
  echo "node ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/node-firewall && \
  chmod 0440 /etc/sudoers.d/node-firewall && \
  echo "node ALL=(root) NOPASSWD: /usr/sbin/dockerd, /usr/bin/dockerd" > /etc/sudoers.d/node-docker && \
  chmod 0440 /etc/sudoers.d/node-docker

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
  -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  -a 'export PATH="/home/node/.local/bin:$PATH"' \
  -x

# ============================================================
# Claude Code CLI
# ============================================================
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}
