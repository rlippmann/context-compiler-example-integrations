# LiteLLM Proxy (pre-call hook)

Saved compiler state changes whether LiteLLM Proxy blocks a request, forwards
it unchanged, or injects compiler state before the downstream call. This
example shows LiteLLM Proxy acting as the host-owned gateway surface.

Context Compiler is the authority layer for saved state. These hooks no longer
derive authority from transcript history. They process only the latest user
turn and rely on host-owned checkpoints for continuity.

Available hook files:

- Basic checkpoint-backed hook: `context_compiler_precall_hook.py`
- Directive-drafter-enabled checkpoint-backed hook:
  `context_compiler_precall_hook_with_directive_drafter.py`

## Runtime behavior

- LiteLLM Proxy is the gateway surface; Context Compiler remains the authority
  layer for saved state.
- By default, the hooks run in stateless mode and process only the latest user
  turn with a fresh engine.
- In explicit persistent mode, the hook resolves a session key, loads a saved
  checkpoint, restores the engine, processes the latest user turn once, and
  saves the resulting checkpoint after every decision, including `clarify`.
- In stateless mode, no continuity is preserved across requests.
- If result is `clarify`, the proxy does not call the downstream model and
  LiteLLM surfaces the clarification as an HTTP 400 response.
- If result is `passthrough`, the proxy forwards the request normally.
- If result is `update`, the proxy injects compiler state as a system message
  and then calls the model.
- Unsupported LiteLLM callback `call_type` values return the original request
  data unchanged.

Optional directive-drafter behavior:

- The drafter runs only on the current/latest user turn.
- The hook restores checkpoints before drafting.
- Heuristic runs first; if no directive is found, LLM fallback is attempted.
- Forwarded upstream request messages are not rewritten except for the injected
  compiler system message.

Model fallback output is structurally validated before handoff. This does not prove that the model interpreted the user correctly. The automated fallback path is experimental pending a separate source-aware acceptance policy and reviewed drafting workflow.

## Session mode and session keys

The reference hooks support two explicit modes:

- `persistent`
  - explicit mode
  - requires a stable session key
  - preserves saved state and pending clarification across requests
- `stateless`
  - default mode
  - processes only the latest user turn
  - preserves no continuity

Set the mode with one of:

- top-level request field `context_compiler_mode`
- env var `CONTEXT_COMPILER_SESSION_MODE`

Persistent mode resolves session keys in this order:

1. `context_compiler_session_key`
2. `metadata.context_compiler_session_key`

If persistent mode cannot resolve a stable session key, the hook fails clearly
and does not fall back to transcript replay or implicit stateless behavior.

## Checkpoint store contract

The hooks share a small repo-local support module:

```python
class CheckpointStore(Protocol):
    def load(self, session_key: str) -> Mapping[str, object] | None: ...
    def save(self, session_key: str, checkpoint: Mapping[str, object]) -> None: ...
```

The reference implementation uses an in-memory store for tests and local demos.
It is single-process only:

- no durability across restarts
- no multi-worker coordination
- no atomic compare-and-swap
- no expiration/cleanup policy

Real deployments should replace it with a host-owned store such as Redis or a
database-backed implementation.

## Requirements

```shell
pip install "context-compiler-example-integrations[litellm]"
export OPENAI_API_KEY=...
```

Start with the compiler-only hook. Add `context-compiler-directive-drafter`
only if you want the optional directive-drafter variant.

For `context_compiler_precall_hook_with_directive_drafter.py`:

```shell
pip install "context-compiler-example-integrations[all]"
```

That variant requires `context-compiler-directive-drafter>=0.1.2`.

For the opt-in runtime smoke test, install the proxy runtime extras:

```shell
uv sync --group proxy_runtime --no-editable
```

## Quickstart (copy/paste)

From the repo root:

```shell
pip install "context-compiler-example-integrations[litellm]"
export OPENAI_API_KEY=...
litellm --config python/reference_integrations/litellm_proxy/config.example.yaml
```

`config.example.yaml` includes both OpenAI and Ollama model definitions.
Use the Ollama model entry for local testing without API credentials.

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
    extra_body={"context_compiler_session_key": "demo-chat"},
)
```

Or with curl:

```shell
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer anything" \
  -d '{
    "model": "gpt-4o-mini",
    "context_compiler_session_key": "demo-chat",
    "messages": [{"role": "user", "content": "prohibit peanuts"}]
  }'
```

For explicit stateless mode:

```json
{
  "model": "gpt-4o-mini",
  "context_compiler_mode": "stateless",
  "messages": [{"role": "user", "content": "prohibit peanuts"}]
}
```

For explicit persistent mode:

```json
{
  "model": "gpt-4o-mini",
  "context_compiler_mode": "persistent",
  "context_compiler_session_key": "demo-chat",
  "messages": [{"role": "user", "content": "prohibit peanuts"}]
}
```

## Run proxy

The reference integration is covered by unit tests and an opt-in runtime smoke
test. See "Opt-in Runtime Smoke Test" below for details.

The proxy runs on `http://localhost:4000` by default. By default,
`config.example.yaml` points to the basic checkpoint-backed hook. To use the
directive-drafter variant, switch the callback path in the config. The callback
path must be importable by LiteLLM in the environment where the proxy process
starts.

When starting LiteLLM from the repo root, prefer fully qualified callback
imports in automated configs, for example:

```text
python.reference_integrations.litellm_proxy.context_compiler_precall_hook.proxy_handler_instance
```

Optional env vars for directive-drafter fallback:

```shell
export PREPROCESSOR_MODEL=openai/gpt-4o-mini
export PREPROCESSOR_PROMPT_PROFILE=default
```

`PREPROCESSOR_MODEL` is optional and defaults to `MODEL`.

For heuristic-first usage, keep `PREPROCESSOR_PROMPT_PROFILE=default`.
Use `llama` only for LLM-only fallback drafting with Llama-family models.

## Notes

- Mixed-content user messages compile only text segments from the latest user
  turn.
- `MODEL` and `PREPROCESSOR_MODEL` use LiteLLM format: `<provider>/<model>`.
- Corrupt or incompatible checkpoints fail clearly in persistent mode and do
  not silently reset state.
- In the directive-drafter hook, drafter state context now comes from restored
  checkpoint state rather than transcript-prefix reconstruction.
- Compound directive-shaped input such as `use docker and prohibit peanuts`
  should produce a local clarify response telling the user to submit each
  directive separately, without mutating saved state or forwarding upstream.

## Troubleshooting

- callback import failures: verify the callback path configured in
  `config.example.yaml` is importable in the current LiteLLM environment
- persistent mode rejects requests: provide a stable session key or opt into
  explicit `stateless` mode
- proxy starts but upstream calls fail: check `OPENAI_API_KEY` and upstream
  model/provider config in `config.example.yaml`
- directive-drafter fallback issues: `PREPROCESSOR_MODEL` defaults to `MODEL`;
  set it explicitly only when using a separate fallback model

## Opt-in Runtime Smoke Test

This repo includes an opt-in runtime smoke test for the LiteLLM Proxy
reference integration. The test starts a real LiteLLM Proxy process, runs the
basic hook and the directive-drafter hook in separate proxy launches, sends
local requests through the proxy with explicit session keys, verifies blocked
requests do not reach upstream, verifies allowed requests reach a local stub
upstream with the injected compiler contract, verifies the directive-drafter
path preserves the original forwarded user prompt text, and shuts each proxy
down cleanly.

It is intentionally not part of `./scripts/validate_python.sh`.

Run it from the repo root:

```shell
RUN_LITELLM_PROXY_RUNTIME=1 uv run --group proxy_runtime pytest python/tests/test_litellm_proxy_runtime.py
```
