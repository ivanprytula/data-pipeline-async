#!/usr/bin/env bash
set -euo pipefail

repo=""
selector=""
watch_checks="false"
perform_merge="false"
merge_method="squash"
delete_branch="false"
discover_required="false"

usage() {
  cat <<'EOF'
Usage:
  guarded-pr-merge.sh [--repo owner/name] [--pr <number|url|branch>] [--watch] [--discover-required] [--merge] [--method squash|merge|rebase] [--delete-branch]

Examples:
  guarded-pr-merge.sh --pr 42
  guarded-pr-merge.sh --watch --pr 42
  guarded-pr-merge.sh --watch --discover-required --merge --method squash --delete-branch

Notes:
  - Default mode validates checks only and never merges.
  - --merge performs the merge only if all required checks pass.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="$2"
      shift 2
      ;;
    --pr)
      selector="$2"
      shift 2
      ;;
    --watch)
      watch_checks="true"
      shift
      ;;
    --discover-required)
      discover_required="true"
      shift
      ;;
    --merge)
      perform_merge="true"
      shift
      ;;
    --method)
      merge_method="$2"
      shift 2
      ;;
    --delete-branch)
      delete_branch="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 1
fi

if [[ -z "$repo" ]]; then
  repo="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi

repo_args=()
if [[ -n "$repo" ]]; then
  repo_args=(--repo "$repo")
fi

if [[ -z "$selector" ]]; then
  selector="$(gh pr view "${repo_args[@]}" --json number -q .number 2>/dev/null || true)"
fi

if [[ -z "$selector" ]]; then
  echo "Could not auto-detect PR. Pass --pr <number|url|branch>." >&2
  exit 1
fi

if [[ "$watch_checks" == "true" ]]; then
  gh pr checks "$selector" "${repo_args[@]}" --watch --interval 10 || true
fi

checks_json="$(gh pr checks "$selector" "${repo_args[@]}" --json name,bucket,state,workflow)"

default_required_json='[
  "01 Quality checks — Python 3.14",
  "02 Unit tests — Python 3.14",
  "03 Verify Alembic migrations (PostgreSQL 17)",
  "04 Integration tests — Python 3.14",
  "05 E2E tests — Python 3.14",
  "06 Dependency Audit"
]'

required_json="$default_required_json"

if [[ "$discover_required" == "true" ]]; then
  discovered="$(echo "$checks_json" | jq -c '
    [
      .[]
      | select(
          .name == "01 Quality checks — Python 3.14"
          or .name == "02 Unit tests — Python 3.14"
          or .name == "03 Verify Alembic migrations (PostgreSQL 17)"
          or .name == "04 Integration tests — Python 3.14"
          or .name == "05 E2E tests — Python 3.14"
            or .name == "06 Dependency Audit"
      )
      | .name
    ]
    | unique
  ')"

  if [[ -n "$discovered" && "$discovered" != "[]" ]]; then
    required_json="$discovered"
    echo "Using auto-discovered required checks from PR context"
  else
    echo "Auto-discovery found no matching checks. Using default required checks." >&2
  fi
fi

echo "Evaluating required checks:"
echo "$required_json" | jq -r '.[]' | sed 's/^/- /'

overall_ok="true"

while IFS= read -r required_name; do
  result="$(echo "$checks_json" | jq -r --arg name "$required_name" '
    [ .[] | select(.name == $name) ] as $matches |
    if ($matches | length) == 0 then
      "missing"
    elif any($matches[]; .bucket == "fail" or .bucket == "cancel") then
      "fail"
    elif any($matches[]; .bucket == "pending") then
      "pending"
    elif any($matches[]; .bucket == "pass" or .bucket == "skipping") then
      "pass"
    else
      "unknown"
    end
  ')"

  case "$result" in
    pass)
      echo "PASS: ${required_name}"
      ;;
    pending)
      echo "PENDING: ${required_name}" >&2
      overall_ok="false"
      ;;
    fail)
      echo "FAIL: ${required_name}" >&2
      overall_ok="false"
      ;;
    missing)
      echo "MISSING: ${required_name}" >&2
      overall_ok="false"
      ;;
    *)
      echo "UNKNOWN: ${required_name}" >&2
      overall_ok="false"
      ;;
  esac
done < <(echo "$required_json" | jq -r '.[]')

if [[ "$overall_ok" != "true" ]]; then
  echo "Guard failed: required checks are not all passing." >&2
  exit 1
fi

echo "Guard passed: all required checks are passing."

if [[ "$perform_merge" == "true" ]]; then
  merge_flag="--squash"
  case "$merge_method" in
    squash) merge_flag="--squash" ;;
    merge) merge_flag="--merge" ;;
    rebase) merge_flag="--rebase" ;;
    *)
      echo "Invalid merge method: ${merge_method}" >&2
      exit 1
      ;;
  esac

  if [[ "$delete_branch" == "true" ]]; then
    gh pr merge "$selector" "${repo_args[@]}" "$merge_flag" --delete-branch
  else
    gh pr merge "$selector" "${repo_args[@]}" "$merge_flag"
  fi

  echo "Merged PR using method: ${merge_method}"
fi
