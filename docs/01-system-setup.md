# System Setup — Required Packages & Tools

> Prerequisites and system-level package installation.
>
> **Time**: 10–20 minutes depending on platform and whether Docker is already installed.

---

## Overview

Data Zoo requires several system-level packages for development, testing, and operations:

| Package                   | Purpose                                        | When Used                                    |
| ------------------------- | ---------------------------------------------- | -------------------------------------------- |
| **Python 3.14+**          | Application runtime                            | Always                                       |
| **uv**                    | Fast Python package manager                    | Always (replaces pip)                        |
| **PostgreSQL Client**     | Database access, backups, queries              | Development, testing, ops                    |
| **Redis CLI**             | Cache inspection and debugging                 | Development, debugging                       |
| **Docker + Compose**      | Container orchestration                        | Development, testing, CI/CD                  |
| **mkcert**                | Local HTTPS certificate generation             | Local development (optional but recommended) |
| **GitHub CLI (`gh`)**     | Manage GitHub Actions vars/secrets/OIDC config | CI/CD operations                             |
| **jq**                    | JSON parsing for API/script automation         | CI/CD operations                             |
| **k3d**                   | Local Kubernetes cluster runtime               | Local K8s deployment testing                 |
| **kubectl**               | Kubernetes API CLI                             | Local K8s operations                         |
| **MongoDB Tools**         | Database backup/restore                        | Operations (optional)                        |
| **util-linux + iproute2** | Chaos testing (network delays, packet loss)    | Advanced testing (optional)                  |

---

## Quick Install by Platform

### macOS

```bash
# Using Homebrew (https://brew.sh if not installed)
brew install python@3.14 uv postgresql redis docker mkcert mongodb-database-tools util-linux iproute2

# CI/CD automation tools
brew install gh jq

# Local Kubernetes tooling (optional, recommended for infra work)
brew install k3d kubectl helm
```

### Ubuntu / Debian

```bash
# Update package lists
sudo apt-get update

# Install packages
sudo apt-get install -y \
  python3.14 python3.14-venv \
  postgresql-client redis-tools \
  docker.io docker-compose \
  mkcert \
  gh jq \
  k3d kubectl helm \
  mongodb-tools \
  util-linux iproute2
```

### Fedora / RHEL

```bash
sudo dnf install -y \
  python3.14 \
  postgresql-contrib redis-tools \
  docker docker-compose \
  mkcert \
  gh jq \
  k3d kubectl helm \
  mongodb-database-tools \
  util-linux iproute2-utils
```

---

## Verify Installation

After installing, verify all packages are available:

```bash
# Python
python3.14 --version

# uv (install separately if not in package manager)
uv --version
  # If not found: pip install uv

# PostgreSQL client
psql --version

# Redis
redis-cli --version

# Docker
docker --version
docker compose version

# mkcert
mkcert --version

# GitHub CLI and jq (used by scripts/ops/01-gh-actions-config.sh)
gh --version
jq --version

# Local Kubernetes tooling
k3d version
kubectl version --client
```

---

## Platform-Specific Notes

### macOS

- **M1/M2 Macs**: All packages above support ARM64. No additional steps needed.
- **Intel Macs**: Compatible as-is.
- **Python 3.14 on macOS**: If Homebrew doesn't have 3.14 yet, use [pyenv](https://github.com/pyenv/pyenv):

  ```bash
  brew install pyenv
  pyenv install 3.14.0
  pyenv local 3.14.0
  ```

### Ubuntu / Debian

- **WSL2 (Windows Subsystem for Linux)**: Fully supported. Install Docker Desktop for Windows, WSL2 backend will provide Docker CLI.
- **Ubuntu 22.04 LTS**: Recommended for best compatibility.
- **Older Ubuntu (20.04)**: Python 3.14 may require third-party PPA:

  ```bash
  sudo apt-get install software-properties-common
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install python3.14
  ```

### Fedora / RHEL / CentOS

- **CentOS 7 (deprecated)**: Not recommended; upgrade to CentOS Stream or RHEL 8+.
- **RHEL 8+**: All packages available in standard repos.

---

## Docker Setup

### Verify Docker Daemon is Running

```bash
docker ps
# Should return container list (possibly empty). If error: daemon not running.
```

### Enable Docker Without sudo (Linux)

By default, Docker requires `sudo`. To run without sudo:

```bash
sudo groupadd docker        # Create docker group (may already exist)
sudo usermod -aG docker $USER  # Add current user to group
newgrp docker               # Activate new group (or log out and back in)
docker ps                   # Should work without sudo now
```

### Docker Compose

Verify `docker compose` command works (not `docker-compose`):

```bash
docker compose version
# If not found, install: pip install docker-compose
```

---

## Next Steps

Once all packages are installed and verified:

1. **Clone the repository** (if not already done)
2. Proceed to **[02 — First-Time Project Setup](02-first-time-setup.md)** to initialize the project

---

## Troubleshooting

### Python 3.14 Not Found

```bash
# Check if Python 3.14 is installed under a different name
ls /usr/bin/python*

# If only 3.13 or earlier exists, install via:
# - macOS: brew install python@3.14
# - Ubuntu: sudo apt-get install python3.14 (may require PPA)
# - Fedora: sudo dnf install python3.14
```

### uv Not in Package Manager

If your platform doesn't package `uv`, install via pip:

```bash
pip install uv
```

### PostgreSQL Client Not Found

The PostgreSQL client is separate from the server. Install:

```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# Fedora/RHEL
sudo dnf install postgresql
```

### Docker Daemon Won't Start

```bash
# macOS: Restart Docker Desktop
open /Applications/Docker.app

# Linux: Restart Docker service
sudo systemctl restart docker

# Verify it's running
docker ps
```

### Permission Denied: /var/run/docker.sock

```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker
docker ps  # Should work now
```

---

## Optional: Advanced Tools

### For Load Testing

```bash
# k6 (modern load testing tool)
# macOS:
brew install k6

# Ubuntu/Debian:
sudo apt-get install k6

# Or via Docker:
docker run grafana/k6 run script.js
```

### For Local Kubernetes Validation

```bash
# Bootstrap local k3d cluster and namespace
bash scripts/setup/03-bootstrap-k3d.sh

# Verify context and nodes
kubectl config current-context
kubectl get nodes
```

### For Debugging & Profiling

```bash
# pgAdmin (PostgreSQL GUI, optional)
brew install pgadmin4  # macOS
# or run via Docker: docker run -p 5050:80 dpage/pgadmin4

# Redis GUI (optional)
# Download from: https://www.redis.com/redis-enterprise/redis-insight/
```

---

## What's Next?

All packages installed? Proceed to **[02 — First-Time Project Setup](02-first-time-setup.md)** to initialize the project locally.
