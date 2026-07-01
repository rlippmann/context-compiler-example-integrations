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

packages=(
  "typescript/examples/checkpoint_continuation"
  "typescript/examples/execution_authorization/expense_approval"
  "typescript/examples/gateway_middleware/customer_support_routing"
  "typescript/examples/prompt_construction/writing_assistant"
  "typescript/examples/retrieval_filtering/hr_policy_lookup"
  "typescript/examples/schema_selection/vercel_ai_sdk_generate_object"
  "typescript/examples/tool_gating/calendar_admin"
  "typescript/examples/tool_gating/mcp_calendar_admin"
  "typescript/starter_apps/node/basic"
  "typescript/starter_apps/node/with_drafter"
)

for package_dir in "${packages[@]}"; do
  echo "==> ${package_dir}"
  pushd "${repo_root}/${package_dir}" >/dev/null
  ensure_package_deps "${package_dir}"
  npm test
  npm run typecheck
  if [[ "${package_dir}" == "typescript/examples/checkpoint_continuation" || "${package_dir}" == "typescript/examples/schema_selection/vercel_ai_sdk_generate_object" || "${package_dir}" == "typescript/examples/execution_authorization/expense_approval" || "${package_dir}" == "typescript/examples/gateway_middleware/customer_support_routing" || "${package_dir}" == "typescript/examples/retrieval_filtering/hr_policy_lookup" || "${package_dir}" == "typescript/examples/prompt_construction/writing_assistant" || "${package_dir}" == "typescript/examples/tool_gating/calendar_admin" || "${package_dir}" == "typescript/examples/tool_gating/mcp_calendar_admin" ]]; then
    npm run build
  fi
  popd >/dev/null
done
