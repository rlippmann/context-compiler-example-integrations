#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ensure_package_deps() {
  local package_dir="$1"

  if [[ ! -d node_modules ]]; then
    echo "installing dependencies for ${package_dir}"
    npm install
  fi
}

fast_packages=(
  "typescript/examples/execution_authorization/expense_approval"
  "typescript/examples/schema_selection/vercel_ai_sdk_generate_object"
  "typescript/starter_apps/node/basic"
  "typescript/starter_apps/node/with_drafter"
)

next_packages=(
  "typescript/starter_apps/nextjs/basic"
  "typescript/starter_apps/nextjs/with_drafter"
)

for package_dir in "${fast_packages[@]}"; do
  echo "==> ${package_dir}"
  pushd "${repo_root}/${package_dir}" >/dev/null
  ensure_package_deps "${package_dir}"
  npm test
  npm run typecheck
  if [[ "${package_dir}" == "typescript/examples/schema_selection/vercel_ai_sdk_generate_object" || "${package_dir}" == "typescript/examples/execution_authorization/expense_approval" ]]; then
    npm run build
  fi
  popd >/dev/null
done

for package_dir in "${next_packages[@]}"; do
  echo "==> ${package_dir}"
  pushd "${repo_root}/${package_dir}" >/dev/null
  ensure_package_deps "${package_dir}"
  npm test
  npm run build
  npm run typecheck
  popd >/dev/null
done
