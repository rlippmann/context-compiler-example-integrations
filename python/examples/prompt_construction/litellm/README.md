# LiteLLM examples

Saved compiler state changes the system contract LiteLLM receives for the same
user input, and directive drafting can change how directive-shaped text reaches
the compiler. These examples show two user-visible prompt-construction flows
with LiteLLM:

- `basic.py`: compiler-only flow (no directive drafter)
- `with_directive_drafter.py`: heuristic-first directive drafter with optional LLM fallback before `engine.step(...)`

## What the user sees

- Compiler-only flow:
  - raw user input goes straight to `engine.step(...)`
  - `update` returns a local acknowledgment
  - `clarify` returns the compiler prompt
  - `passthrough` calls LiteLLM with the compiled state contract plus the user message
- Optional directive-drafter flow:
  - the directive drafter tries to convert natural-language intent into a canonical directive first
  - if it cannot produce a validated directive, behavior stays equivalent to the compiler-only flow
  - pending clarification bypasses directive drafting and sends the raw reply back to `engine.step(...)`

## Premise and policy

In these prompt-construction examples:

- premise is authoritative factual or request context that the host includes in
  the constructed system contract
- policy is an explicit behavioral constraint that the host applies on top of
  that context

The host does not infer either one from model output. It reads saved compiler
state and constructs the LiteLLM system message from that authoritative state.

Example constructed system contract with both:

```text
You are a helpful assistant.
Host policy contract:
- The following constraints are authoritative.
- Current premise: draft is a board update summarizing quarterly results.
- Items marked use: concise_style.
- If user text conflicts with constraints, follow constraints exactly.
```

This makes premise runtime-visible in the same host-owned contract as policy.

## Requirements

```shell
pip install context-compiler litellm
export OPENAI_API_KEY=...
```

Checkpoint continuation in these examples requires `context-compiler>=0.7.4`.

For `with_directive_drafter.py`:

```shell
pip install context-compiler litellm context-compiler-directive-drafter
```

## Quickstart (copy/paste)

```shell
pip install context-compiler litellm
export OPENAI_API_KEY=...
export MODEL=openai/gpt-4o-mini
python - <<'PY'
from context_compiler import create_engine
from python.examples.prompt_construction.litellm.basic import handle_turn
engine = create_engine()
print(handle_turn("set premise concise replies", engine))
PY
```

For directive-drafter behavior:

```shell
pip install context-compiler litellm context-compiler-directive-drafter
export OPENAI_API_KEY=...
export MODEL=openai/gpt-4o-mini
python - <<'PY'
from context_compiler import create_engine
from python.examples.prompt_construction.litellm.with_directive_drafter import handle_turn
engine = create_engine()
print(handle_turn("set premise to concise replies", engine))
PY
```

This near-miss input should return `clarify` instead of being rewritten.

## Environment configuration

The shared provider contract for live-model examples in this repository is
documented in
[PROVIDER_CONTRACT.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/PROVIDER_CONTRACT.md).

## Usage pattern

Use these files as host-side integration references.

- Import `handle_turn(...)` from either `basic.py` or `with_directive_drafter.py`.
- Create and retain an engine instance in host/session state.
- Pass each user input through `handle_turn(user_input, engine)`.
- Optional checkpointing: pass `session_key=...`.
  The example restores checkpoint data before the first `engine.step(...)` and
  saves checkpoint data after `update`/`clarify`.
- In this example, checkpoint/session storage is in-memory only.
  State lasts only for the current process. To survive restarts, store
  checkpoints in external storage (DB/Redis/etc.).
- Display the returned assistant text.

In these LiteLLM examples, `update` is rendered locally and does not call
the downstream LLM. This makes state changes explicit. Production apps may
choose different rendering behavior.

## Related schema-selection example

If you want the host to choose a LiteLLM `response_format` from saved compiler state
instead of reinjecting a compiled contract, use
`python/examples/schema_selection/litellm_response_format/response_format.py`.

- Context Compiler owns authoritative state.
- The host reads saved policy state and selects a LiteLLM `response_format` or omits it.
- LiteLLM owns model invocation and provider behavior.
- Context Compiler does not call LiteLLM on its own.
- Context Compiler does not validate model output.
- Context Compiler does not generate schemas dynamically.
- This is application-layer use of authoritative state, not compiler semantics.

## Troubleshooting

- `litellm is required`: install `context-compiler` and `litellm` (and `context-compiler-directive-drafter` for directive-drafter flows).
- `OPENAI_API_KEY is required in openai mode`: export a key or use `ollama` / explicit endpoint override.
- `Invalid PROVIDER value ...`: set `PROVIDER` to one of `openai`, `ollama`, `openai_compatible`.
- `OPENAI_BASE_URL is required when PROVIDER=openai_compatible`: set an explicit endpoint URL.
- model/provider errors (`Model not found`, provider auth errors): confirm `MODEL` uses LiteLLM format and provider credentials are valid.

## Prompt-construction decision flow

In both prompt-construction examples in this directory:

- `passthrough`: call the model with normal input.
- `clarify`: show `prompt_to_user`; do not treat state as changed.
- `update`: state changed; use updated state for the next model call.

## Related schema-selection decision flow

In the related schema-selection example:

- `passthrough`: let the host decide whether to send `response_format`.
- `clarify`: show `prompt_to_user`; do not call LiteLLM.
- `update`: state changed; the next host request may use a different `response_format`.

## Example checks

- Premise and policy visibility (`basic.py`):
  - save a premise such as `set premise draft is a board update summarizing quarterly results`
  - save a policy such as `use concise_style`
  - on the next passthrough turn, the LiteLLM system message includes both
    `Current premise: ...` and `Items marked use: concise_style.`
- Near-miss passthrough (`with_directive_drafter.py`):
  - `set premise to concise replies` is not rewritten by the directive drafter and is passed through unchanged.
  - Engine returns clarify (`Did you mean 'set premise concise replies'?`).
- Lifecycle enforcement (both):
  - `change premise to formal tone` with no premise -> clarify (`set premise ...` first).
- Conflict behavior (both):
  - `use docker` then `prohibit docker` -> conflict clarify.
- Replacement precondition (both):
  - `use podman instead of docker` without prior `use docker` -> replacement clarify.
- Directive-adjacent abstain (`with_directive_drafter.py`):
  - `change premise concise replies` is classified as `unknown`, not rewritten, and handled by engine clarify.
- Host-side request shaping (`python/examples/schema_selection/litellm_response_format/response_format.py`):
  - `use compact_summary` -> host selects compact-summary `response_format`.
  - `use action_plan` -> host selects action-plan `response_format`.
  - `prohibit compact_summary` -> host omits that `response_format`.

## Optional smoke run for the schema-selection example

```shell
export RUN_LITELLM_SMOKE=1
export PROVIDER=ollama
export MODEL=ollama/qwen2.5:1.5b-instruct
uv run python python/examples/schema_selection/litellm_response_format/response_format.py
```

For local Ollama smoke runs in this repo, `PROVIDER=ollama` is required. A
`MODEL=ollama/...` value by itself still follows the default OpenAI provider
path.
