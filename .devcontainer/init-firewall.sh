#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# 1. Save full Docker iptables state BEFORE any flushing
DOCKER_IPTABLES_SAVE=$(iptables-save 2>/dev/null || true)

# Flush existing rules and delete existing ipsets
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# 2. Restore Docker iptables chains (filter, nat, mangle)
# Docker creates chains like DOCKER, DOCKER-FORWARD, DOCKER-ISOLATION-STAGE-*
# that must exist for Docker networking to work
if [ -n "$DOCKER_IPTABLES_SAVE" ]; then
    echo "Restoring Docker iptables chains..."
    echo "$DOCKER_IPTABLES_SAVE" | iptables-restore --noflush 2>/dev/null || {
        echo "WARNING: Could not fully restore Docker iptables, dockerd will recreate on restart" >&2
    }
else
    echo "No Docker iptables state to restore"
fi

# First allow DNS and localhost before any restrictions
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Create ipset with CIDR support
ipset create allowed-domains hash:net

# Fetch GitHub meta information and aggregate + add their IP ranges
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s https://api.github.com/meta)
if [ -z "$gh_ranges" ]; then
    echo "ERROR: Failed to fetch GitHub IP ranges" >&2
    exit 1
fi

if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
    echo "ERROR: GitHub API response missing required fields" >&2
    exit 1
fi

echo "Processing GitHub IPs..."
while read -r cidr; do
    if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        echo "ERROR: Invalid CIDR range from GitHub meta: $cidr" >&2
        exit 1
    fi
    echo "Adding GitHub range $cidr"
    ipset add allowed-domains "$cidr"
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | aggregate -q)

# Resolve and add allowed domains
for domain in \
    "registry.npmjs.org" \
    "api.anthropic.com" \
    "sentry.io" \
    "statsig.anthropic.com" \
    "statsig.com" \
    "marketplace.visualstudio.com" \
    "vscode.blob.core.windows.net" \
    "update.code.visualstudio.com" \
    "pypi.org" \
    "files.pythonhosted.org" \
    "astral.sh" \
    "dl.k8s.io" \
    "cdn.dl.k8s.io" \
    "storage.googleapis.com" \
    "kind.sigs.k8s.io" \
    "ghcr.io" \
    "pkg-containers.githubusercontent.com" \
    "get.helm.sh" \
    "github.com" \
    "objects.githubusercontent.com" \
    "raw.githubusercontent.com" \
    "prometheus-community.github.io" \
    "charts.bitnami.com" \
    "repo.broadcom.com" \
    "dagster-io.github.io" \
    "registry-1.docker.io" \
    "auth.docker.io" \
    "production.cloudflare.docker.com" \
    "docker-images-prod.6aa30f8b08e16409b46e0173d6de2f56.r2.cloudflarestorage.com" \
    "deb.debian.org" \
    "security.debian.org" \
    "cdn-fastly.deb.debian.org" \
    "docker.io" \
    "index.docker.io" \
    ; do
    echo "Resolving $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $domain (may be CNAME-only, skipping)" >&2
        continue
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "ERROR: Invalid IP from DNS for $domain: $ip" >&2
            exit 1
        fi
        echo "Adding $ip for $domain"
        ipset add allowed-domains "$ip" 2>/dev/null || true
    done < <(echo "$ips")
done

# Get host IP from default route
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP" >&2
    exit 1
fi

HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
echo "Host network detected as: $HOST_NETWORK"

# Allow host network (needed for Docker-in-Docker and Kind)
iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

# Allow Docker-in-Docker networks (172.17.0.0/16 and 172.18.0.0/16)
# Kind creates docker networks in these ranges
iptables -A INPUT -s 172.16.0.0/12 -j ACCEPT
iptables -A OUTPUT -d 172.16.0.0/12 -j ACCEPT

# Allow Kind pod and service CIDRs (from kind-config.yaml)
iptables -A INPUT -s 10.244.0.0/16 -j ACCEPT
iptables -A OUTPUT -d 10.244.0.0/16 -j ACCEPT
iptables -A INPUT -s 10.96.0.0/16 -j ACCEPT
iptables -A OUTPUT -d 10.96.0.0/16 -j ACCEPT

# Set default policies to DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow FORWARD for Docker-in-Docker (Kind needs container-to-container traffic)
iptables -A FORWARD -s 172.16.0.0/12 -j ACCEPT
iptables -A FORWARD -d 172.16.0.0/12 -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow outbound to allowed domains
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Reject everything else
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "Firewall configuration complete"
echo "Verifying firewall rules..."
if curl --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - was able to reach https://example.com" >&2
    exit 1
else
    echo "Firewall verification passed - unable to reach https://example.com as expected"
fi

if ! curl --connect-timeout 5 https://api.github.com/zen >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - unable to reach https://api.github.com" >&2
    exit 1
else
    echo "Firewall verification passed - able to reach https://api.github.com as expected"
fi
