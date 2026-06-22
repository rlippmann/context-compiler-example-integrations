#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

packages=(
  "typescript/examples/schema_selection/vercel_ai_sdk_generate_object"
  "typescript/starter_apps/node/basic"
  "typescript/starter_apps/node/with_drafter"
)

for package_dir in "${packages[@]}"; do
  echo "==> ${package_dir}"
  pushd "${repo_root}/${package_dir}" >/dev/null
  npm test
  npm run typecheck
  if [[ "${package_dir}" == "typescript/examples/schema_selection/vercel_ai_sdk_generate_object" ]]; then
    npm run build
  fi
  popd >/dev/null
done
