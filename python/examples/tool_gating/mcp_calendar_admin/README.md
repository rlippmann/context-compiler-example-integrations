# `mcp_calendar_admin`

Authoritative state changes whether the host exposes and executes the calendar
admin MCP tool. This example shows tool gating with MCP as the integration
surface.

Context Compiler owns the authoritative policy state that decides whether the
host exposes the calendar admin MCP tool.

The host exposes and allows `calendar_admin_create_event` only when state
contains:

```text
use calendar_admin
```

The host omits that tool from the exposed MCP tool set when state is absent or
when state contains:

```text
prohibit calendar_admin
```

If a caller still invokes the hidden tool directly, the host blocks execution.

Adversarial request text does not expose the tool or mutate policy state.

The provider-free tests are the canonical proof for this example.

This example also includes an opt-in live-model comparison that shows the same
admin-calendar intent reaches different outcomes because authoritative Context
Compiler state changes the model-visible tool surface.

## Live-model comparison

The live-model path keeps the same host-owned MCP tool registry and execution
rules.

The host exposes only the MCP tools allowed by authoritative state, then asks a
real tool-calling model to complete the same admin action.

The model can only use the tools the host exposes.

This is not prompt reinjection:

- the host does not derive authority from model output
- the model does not create or mutate authoritative state
- Context Compiler state determines whether the protected admin tool is visible
  and executable

### Same request, different state

User intent:

```text
Create an admin calendar event named Quarterly access review on calendar ops-admin.
```

Outcome matrix:

- absent state: protected tool is not exposed, and no protected side effect
  occurs
- `use calendar_admin`: protected tool is exposed; if the model selects it, the
  host executes it and writes one side effect
- contradiction with `prohibit calendar_admin`: Context Compiler returns
  clarify/conflict and blocks protected execution before tool execution

### Validation

Canonical provider-free tests:

```bash
uv run --no-sync pytest python/tests/test_mcp_calendar_admin_tool_gating_example.py
uv run --no-sync pytest python/tests/test_mcp_calendar_admin_live_model_helper.py
```

Opt-in live-model validation:

```bash
export RUN_MCP_CALENDAR_ADMIN_LIVE_MODEL=1
export MODEL=openai/gpt-4o-mini
export OPENAI_API_KEY=...
uv run --no-sync pytest python/tests/test_mcp_calendar_admin_live_model.py
```

This live-model path uses the shared provider contract documented in
[PROVIDER_CONTRACT.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/PROVIDER_CONTRACT.md).

Example-specific note for local Ollama:

- this example accepts either `PROVIDER=ollama` with a bare `MODEL` such as
  `qwen2.5:1.5b-instruct`
- or an explicit LiteLLM-style `MODEL=ollama/qwen2.5:1.5b-instruct`
