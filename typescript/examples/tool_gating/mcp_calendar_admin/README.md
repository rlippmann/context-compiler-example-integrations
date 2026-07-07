# `mcp_calendar_admin`

This example shows tool gating where MCP is the integration surface and the
host owns the MCP registry plus MCP tool execution.

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

The provider-free tests remain the canonical proof for this example.

This example also includes an opt-in live-model comparison that keeps the same
host-owned MCP registry and execution rules while letting a real model choose
from the exposed MCP tool surface.

## Live-model validation

The host builds the exposed MCP tool list from authoritative Context Compiler
state and passes only those tools to the model.

The live-model helper is a plain TypeScript HTTP client. It uses an
OpenAI-compatible request shape for tool calling. It does not use the OpenAI
SDK, LiteLLM, or Ollama's native `/api/chat` route.

Use the same intent across states:

```text
Create an admin calendar event named Quarterly access review on calendar ops-admin.
```

What to observe:

- absent state: the protected admin tool is not exposed and no protected side
  effect occurs
- `use calendar_admin`: the protected tool is exposed; the model must select it
  for protected execution to occur
- contradiction with `prohibit calendar_admin`: clarification blocks protected
  execution before tool use

Run the canonical provider-free tests:

```bash
npm test
```

Run the opt-in live-model validation:

```bash
export RUN_MCP_CALENDAR_ADMIN_LIVE_MODEL=1
export OPENAI_API_KEY=...
export MODEL=gpt-4o-mini
npm test -- --test-name-pattern="live model tool surface changes with authoritative state"
```

HTTP contract:

- `MODEL` is sent as-is to the target OpenAI-compatible endpoint
- `OPENAI_API_KEY` is required for the live-model HTTP call

For the shared provider contract used across live-model examples in this repo,
see
[python/examples/prompt_construction/litellm/README.md](../../../../python/examples/prompt_construction/litellm/README.md).

Run the same opt-in validation with local Ollama:

```bash
export RUN_MCP_CALENDAR_ADMIN_LIVE_MODEL=1
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=ollama
export MODEL=qwen2.5:1.5b-instruct
npm test -- --test-name-pattern="live model tool surface changes with authoritative state"
```
