#!/usr/bin/env bash
# harness: reusable
# Run a command in the dev environment.
#
# ============================================================================
# EXAMPLE — adapt to your project's toolchain.
#
# This script ships with the agent-harness as a generic wrapper for
# containerized development. The pattern
# (in-container path vs local-docker path, with a dune-workspace check)
# is reusable; the toolchain calls (opam env, dune-workspace) are not.
#
# When porting:
# 1. Replace `eval "$(opam env)"` with your toolchain init (cargo,
#    nvm use, source venv, etc.) or remove if not needed.
# 2. Replace `dune-workspace` existence check with your project's
#    workspace root marker (Cargo.toml, package.json, pyproject.toml).
# 3. Replace PROJECT_CONTAINER_NAME default with your container name.
# 4. Replace PROJECT_IN_CONTAINER env-var name with your project's
#    equivalent, or rename to something generic like AGENT_HARNESS_IN_ENV.
# 5. Replace /workspaces/<PROJECT_NAME> docker-root path with your container's
#    mount point.
#
# The split between in-container (GHA / devcontainer) and local-docker
# (developer machine) is the load-bearing pattern; the rest is example.
# ============================================================================
#
# Usage:
#   dev/lib/run-in-env.sh <build_cmd>
#   dev/lib/run-in-env.sh <test_cmd> <path>
#
# Locally (default): wraps with `docker exec` into <PROJECT_NAME>-dev,
# cd's to the workspace, and sources opam env.
#
# In GHA / devcontainer: set PROJECT_IN_CONTAINER=1 and the script
# runs natively (cd + toolchain init, no docker wrapping).
#
# Project root resolution (in-container path):
#   GHA:   ${GITHUB_WORKSPACE}  — repo checks out at GITHUB_WORKSPACE.
#   Local container / other: resolve relative to this script's location.
#          The script lives at <repo-root>/dev/lib/; climb two levels to reach
#          the repo root.
#
# Both paths verify that <PROJECT_ROOT_MARKER> exists at the resolved root and fail
# loudly if it doesn't — this catches path mismatches rather than silently
# running commands in the wrong directory.

set -euo pipefail

CONTAINER_NAME="${PROJECT_CONTAINER_NAME:-<PROJECT_NAME>-dev}"

if [ $# -eq 0 ]; then
  echo "Usage: dev/lib/run-in-env.sh <command> [args...]" >&2
  exit 1
fi

if [ -n "${PROJECT_IN_CONTAINER:-}" ]; then
  # --- In-container path (GHA or devcontainer) ---

  if [ -n "${GITHUB_WORKSPACE:-}" ]; then
    # GHA: the repo is checked out at $GITHUB_WORKSPACE.
    PROJECT_ROOT="${GITHUB_WORKSPACE}"
  else
    # Devcontainer / fallback: resolve relative to this script's location.
    # The script lives at <repo-root>/dev/lib/run-in-env.sh.
    # Climb two levels to reach the repo root.
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_ROOT="$(cd "${script_dir}/../.." && pwd)"
  fi

  # Fail loudly rather than run in the wrong directory.
  # Replace <PROJECT_ROOT_MARKER> with your workspace root file (e.g. package.json).
  if [ ! -f "${PROJECT_ROOT}/<PROJECT_ROOT_MARKER>" ]; then
    echo "run-in-env.sh: no <PROJECT_ROOT_MARKER> at ${PROJECT_ROOT}" >&2
    echo "  (expected workspace root; check PROJECT_ROOT derivation)" >&2
    echo "  PROJECT_ROOT=${PROJECT_ROOT}" >&2
    exit 1
  fi

  cd "$PROJECT_ROOT"
  <TOOLCHAIN_INIT_CMD>
  exec "$@"
else
  # --- Local path: delegate to docker exec ---

  # The container mounts the repo at /workspaces/<PROJECT_NAME>/.
  DOCKER_PROJECT_ROOT="/workspaces/<PROJECT_NAME>"

  # Forward project-specific env vars to the container. Comma-separated list
  # of names; defaults to empty. Adapt to your project's secrets / API keys.
  DOCKER_ENV_FLAGS=""
  IFS=',' read -ra forward <<< "${RUN_IN_ENV_FORWARD:-}"
  for var in "${forward[@]}"; do
    [ -n "$var" ] && [ -n "${!var:-}" ] && DOCKER_ENV_FLAGS="$DOCKER_ENV_FLAGS -e $var"
  done
  exec docker exec $DOCKER_ENV_FLAGS "$CONTAINER_NAME" bash -c \
    "cd $DOCKER_PROJECT_ROOT && <TOOLCHAIN_INIT_CMD> && $*"
fi
