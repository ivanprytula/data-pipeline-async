#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset
set -o errtrace

info() {
  printf '[INFO] %s\n' "$*" >&2
}

error() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || error "Required command not found: $1"
}

usage() {
  cat <<'EOF'
Usage:
  gh-actions-config.sh vars set <name> <value> [--env <environment>] [--repo <owner/repo>]
  gh-actions-config.sh vars delete <name> [--env <environment>] [--repo <owner/repo>]
  gh-actions-config.sh vars list [--env <environment>] [--repo <owner/repo>]

  gh-actions-config.sh secrets set <name> <value> [--env <environment>] [--repo <owner/repo>]
  gh-actions-config.sh secrets delete <name> [--env <environment>] [--repo <owner/repo>]
  gh-actions-config.sh secrets list [--env <environment>] [--repo <owner/repo>]

  gh-actions-config.sh oidc get [--repo <owner/repo>]
  gh-actions-config.sh oidc set --claims <csv_claim_keys> [--repo <owner/repo>]
  gh-actions-config.sh oidc reset [--repo <owner/repo>]

Examples:
  gh-actions-config.sh vars set AWS_REGION eu-central-1 --repo owner/repo
  gh-actions-config.sh vars set ECS_CLUSTER_NAME data-zoo-dev --env dev
  gh-actions-config.sh secrets set SENTRY_AUTH_TOKEN "$SENTRY_AUTH_TOKEN" --env prod
  gh-actions-config.sh oidc set --claims repo,context,job_workflow_ref
EOF
}

parse_common_args() {
  TARGET_REPO=""
  TARGET_ENV=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)
        [[ $# -ge 2 ]] || error "--repo requires a value"
        TARGET_REPO="$2"
        shift 2
        ;;
      --env)
        [[ $# -ge 2 ]] || error "--env requires a value"
        TARGET_ENV="$2"
        shift 2
        ;;
      *)
        REMAINING_ARGS+=("$1")
        shift
        ;;
    esac
  done
}

build_repo_args() {
  REPO_ARGS=()
  if [[ -n "${TARGET_REPO}" ]]; then
    REPO_ARGS=(--repo "${TARGET_REPO}")
  fi
}

vars_set() {
  local name="$1"
  local value="$2"
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh variable set "$name" --env "$TARGET_ENV" --body "$value" "${REPO_ARGS[@]}"
  else
    gh variable set "$name" --body "$value" "${REPO_ARGS[@]}"
  fi
}

vars_delete() {
  local name="$1"
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh variable delete "$name" --env "$TARGET_ENV" "${REPO_ARGS[@]}" --yes
  else
    gh variable delete "$name" "${REPO_ARGS[@]}" --yes
  fi
}

vars_list() {
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh variable list --env "$TARGET_ENV" "${REPO_ARGS[@]}"
  else
    gh variable list "${REPO_ARGS[@]}"
  fi
}

secrets_set() {
  local name="$1"
  local value="$2"
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh secret set "$name" --env "$TARGET_ENV" --body "$value" "${REPO_ARGS[@]}"
  else
    gh secret set "$name" --body "$value" "${REPO_ARGS[@]}"
  fi
}

secrets_delete() {
  local name="$1"
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh secret delete "$name" --env "$TARGET_ENV" "${REPO_ARGS[@]}"
  else
    gh secret delete "$name" "${REPO_ARGS[@]}"
  fi
}

secrets_list() {
  build_repo_args

  if [[ -n "${TARGET_ENV}" ]]; then
    gh secret list --env "$TARGET_ENV" "${REPO_ARGS[@]}"
  else
    gh secret list "${REPO_ARGS[@]}"
  fi
}

oidc_get() {
  build_repo_args
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2026-03-10" \
    "repos/{owner}/{repo}/actions/oidc/customization/sub" \
    "${REPO_ARGS[@]}"
}

oidc_set() {
  local claims_csv="$1"
  build_repo_args

  IFS=',' read -r -a claims <<< "$claims_csv"
  [[ ${#claims[@]} -gt 0 ]] || error "At least one claim key is required"

  local api_args
  api_args=(
    --method PUT
    -H "Accept: application/vnd.github+json"
    -H "X-GitHub-Api-Version: 2026-03-10"
    "repos/{owner}/{repo}/actions/oidc/customization/sub"
  )

  if [[ ${#REPO_ARGS[@]} -gt 0 ]]; then
    api_args+=("${REPO_ARGS[@]}")
  fi

  api_args+=(-f use_default=false)

  local claim
  for claim in "${claims[@]}"; do
    api_args+=(-f "include_claim_keys[]=${claim}")
  done

  gh api "${api_args[@]}"

  info "OIDC subject template updated"
}

oidc_reset() {
  build_repo_args
  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2026-03-10" \
    "repos/{owner}/{repo}/actions/oidc/customization/sub" \
    "${REPO_ARGS[@]}" \
    -f use_default=true

  info "OIDC subject template reset to default"
}

main() {
  require_command gh
  require_command jq

  [[ $# -ge 1 ]] || {
    usage
    exit 1
  }

  local resource="$1"
  shift

  [[ $# -ge 1 ]] || error "Missing action"
  local action="$1"
  shift

  REMAINING_ARGS=()
  parse_common_args "$@"

  case "$resource:$action" in
    vars:set)
      [[ ${#REMAINING_ARGS[@]} -eq 2 ]] || error "vars set requires <name> <value>"
      vars_set "${REMAINING_ARGS[0]}" "${REMAINING_ARGS[1]}"
      ;;
    vars:delete)
      [[ ${#REMAINING_ARGS[@]} -eq 1 ]] || error "vars delete requires <name>"
      vars_delete "${REMAINING_ARGS[0]}"
      ;;
    vars:list)
      [[ ${#REMAINING_ARGS[@]} -eq 0 ]] || error "vars list takes no positional arguments"
      vars_list
      ;;
    secrets:set)
      [[ ${#REMAINING_ARGS[@]} -eq 2 ]] || error "secrets set requires <name> <value>"
      secrets_set "${REMAINING_ARGS[0]}" "${REMAINING_ARGS[1]}"
      ;;
    secrets:delete)
      [[ ${#REMAINING_ARGS[@]} -eq 1 ]] || error "secrets delete requires <name>"
      secrets_delete "${REMAINING_ARGS[0]}"
      ;;
    secrets:list)
      [[ ${#REMAINING_ARGS[@]} -eq 0 ]] || error "secrets list takes no positional arguments"
      secrets_list
      ;;
    oidc:get)
      [[ ${#REMAINING_ARGS[@]} -eq 0 ]] || error "oidc get takes no positional arguments"
      oidc_get
      ;;
    oidc:set)
      [[ ${#REMAINING_ARGS[@]} -eq 2 && ${REMAINING_ARGS[0]} == "--claims" ]] || error "oidc set requires --claims <csv_claim_keys>"
      oidc_set "${REMAINING_ARGS[1]}"
      ;;
    oidc:reset)
      [[ ${#REMAINING_ARGS[@]} -eq 0 ]] || error "oidc reset takes no positional arguments"
      oidc_reset
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
