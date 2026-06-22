# LiteLLM Proxy (pre-call hook)

This example shows how a LiteLLM proxy can enforce saved compiler state before
any upstream model call.

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

Hook behavior and proxy startup were re-validated end-to-end with
`litellm==1.88.2`.

Validated behaviors:

- passthrough: upstream model called normally
- update: compiler state injected before upstream model call
- clarify: request blocked before upstream model call and surfaced as HTTP 400

The proxy runs on `http://localhost:4000` by default.
By default, `config.example.yaml` points to the basic replay-only hook.
To use the directive-drafter variant, switch the callback path in the config.
The callback path must be importable by LiteLLM in the environment where the
proxy process starts.

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

## What the user sees

- User messages are replayed through Context Compiler before the model call.
- If result is `clarify`, the proxy does not call the model and LiteLLM surfaces the clarification as an HTTP 400 response.
- If result is `passthrough`, the proxy forwards the request normally.
- If result is `update`, the proxy injects compiler state as a system message and then calls the model.
- Unsupported LiteLLM callback `call_type` values return the original request data unchanged.

Optional directive-drafter behavior:

- Only the latest user transcript message is drafted for compiler replay input.
- Heuristic runs first; if no directive is found, LLM fallback is attempted.
- Forwarded upstream request messages are not rewritten (except injected compiler system message).

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
