# LiteLLM Proxy (pre-call hook)

This example shows how LiteLLM Proxy acts as the host-owned gateway surface.

Context Compiler is the authority layer for saved state.

The pre-call hook enforces that authoritative state before any downstream
model call.

Available hook files:

- Basic replay-only hook: `context_compiler_precall_hook.py`
- Directive-drafter-enabled hook: `context_compiler_precall_hook_with_directive_drafter.py`

## Requirements

```shell
pip install context-compiler litellm
export OPENAI_API_KEY=...
```

Start with the compiler-only hook. Add `context-compiler-directive-drafter`
only if you want the optional directive-drafter variant.

For `context_compiler_precall_hook_with_directive_drafter.py`:

```shell
pip install context-compiler litellm context-compiler-directive-drafter
```

For the opt-in runtime smoke test, install the proxy runtime extras:

```shell
uv sync --group proxy_runtime
```

## Quickstart (copy/paste)

From the repo root:

```shell
pip install context-compiler litellm
export OPENAI_API_KEY=...
litellm --config python/reference_integrations/litellm_proxy/config.example.yaml
```

`config.example.yaml` includes both OpenAI and Ollama model definitions.
Use the Ollama model entry for local testing without API credentials.

## Run proxy

Typical startup command (environment-sensitive):

```shell
litellm --config python/reference_integrations/litellm_proxy/config.example.yaml
```

The reference integration is covered by unit tests and an opt-in runtime
smoke test. See "Opt-in Runtime Smoke Test" below for details.

Validated basic-hook behaviors:

- passthrough: upstream model called normally
- update: compiler state injected before upstream model call
- confirm: request blocked before upstream model call and surfaced as HTTP 400

The proxy runs on `http://localhost:4000` by default.
By default, `config.example.yaml` points to the basic replay-only hook.
To use the directive-drafter variant, switch the callback path in the config.
The callback path must be importable by LiteLLM in the environment where the
proxy process starts.

When starting LiteLLM from the repo root, prefer fully qualified callback
imports in automated configs, for example:

```text
python.reference_integrations.litellm_proxy.context_compiler_precall_hook.proxy_handler_instance
```

## Make a request

```python
from openai import OpenAI

client = OpenAI(
    api_key="anything",
    base_url="http://localhost:4000",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "prohibit peanuts"}],
)
```

Or with curl:

```shell
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer anything" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "prohibit peanuts"}]
  }'
```

## Runtime behavior

- User messages are replayed through Context Compiler before the model call.
- LiteLLM Proxy is the gateway surface; Context Compiler remains the authority layer for saved state.
- If result is `confirm`, the proxy does not call the downstream model and LiteLLM surfaces the confirmation as an HTTP 400 response.
- If result is `passthrough`, the proxy forwards the request normally.
- If result is `update`, the proxy injects compiler state as a system message and then calls the model.
- Unsupported LiteLLM callback `call_type` values return the original request data unchanged.

Optional directive-drafter behavior:

- Only the latest user transcript message is drafted for compiler replay input.
- Heuristic runs first; if no directive is found, LLM fallback is attempted.
- Forwarded upstream request messages are not rewritten (except injected compiler system message).

Runtime verification boundary:

- Basic hook: opt-in runtime smoke test covers proxy startup, blocked request behavior, and forwarded contract injection at the LiteLLM Proxy runtime boundary.
- Directive-drafter hook: opt-in runtime smoke test covers the same proxy boundary behaviors, plus verifies drafting only changes compiler replay input and does not rewrite the forwarded upstream request payload.
- Directive-drafter fallback model behavior remains environment-sensitive and is primarily covered by unit-style tests rather than this local stub runtime smoke path.

Optional env vars for directive-drafter fallback:

```shell
export PREPROCESSOR_MODEL=openai/gpt-4o-mini
export PREPROCESSOR_PROMPT_PROFILE=default
```

`PREPROCESSOR_MODEL` is optional and defaults to `MODEL`.

For heuristic-first usage, keep `PREPROCESSOR_PROMPT_PROFILE=default`.
Use `llama` only for LLM-only preprocessing with Llama-family models.

## Notes

- Mixed-content user messages replay only text segments into compiler transcript state.
- `MODEL` and `PREPROCESSOR_MODEL` use LiteLLM format: `<provider>/<model>`.

## Troubleshooting

- Callback import failures: verify the callback path configured in `config.example.yaml` is importable in the current LiteLLM environment.
- proxy starts but upstream calls fail: check `OPENAI_API_KEY` and upstream model/provider config in `config.example.yaml`.
- directive-drafter fallback issues: `PREPROCESSOR_MODEL` defaults to `MODEL`; set it explicitly only when using a separate fallback model.

## Opt-in Runtime Smoke Test

This repo includes an opt-in Tier 2 runtime smoke test for the LiteLLM Proxy
reference integration. The test starts a real LiteLLM Proxy process, runs the
basic hook and the directive-drafter hook in separate proxy launches, sends
local requests through the proxy, verifies blocked requests do not reach
upstream, verifies allowed requests reach a local stub upstream with the
injected compiler contract, verifies the directive-drafter path preserves the
original forwarded user prompt text, and shuts each proxy down cleanly.

It is intentionally not part of `./scripts/validate_python.sh`.

Run it from the repo root:

```shell
RUN_LITELLM_PROXY_RUNTIME=1 uv run --group proxy_runtime pytest python/tests/test_litellm_proxy_runtime.py
```
