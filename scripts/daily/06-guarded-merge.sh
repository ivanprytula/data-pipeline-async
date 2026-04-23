#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/../.." && pwd)"
guard_script="${project_root}/scripts/tools/guarded-pr-merge.sh"

if [[ ! -x "${guard_script}" ]]; then
  chmod +x "${guard_script}"
fi

"${guard_script}" "$@"
