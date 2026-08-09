# Open WebUI Pipe Integration

Saved compiler state changes which turns the pipe handles locally and what it
forwards downstream. These examples show Open WebUI pipe behavior with and
without Directive Drafter preprocessing.

## Core behavior

- The pipe handles directive-only turns locally and returns a fixed response.
- The pipe forwards normal chat turns to the backend model.
- When compiler state is non-empty, passthrough includes exactly one compiler-owned
  `[[cc_state]]` system message in the forwarded request.
- Conflicting or invalid updates are rejected for the current request and do not
  create resumable continuation state.
- The pipe handles exact `show state` locally. The pipe treats near matches such
  as `show state please` as normal chat input.

The forwarded `[[cc_state]]` block makes both kinds of authoritative state
runtime-visible:

- premise = authoritative factual or request context
- policy = explicit behavioral constraint

Example forwarded state block with both:

```text
[[cc_state]]
Premise: draft is a board update summarizing quarterly results
Use: concise_style
Prohibit: slang
```

The host injects this block into the forwarded request. Premise is not only a
syntax or lifecycle rule here; it is part of the runtime-visible state that
shapes the downstream request.

## Files

- `open_webui_pipe.py`: basic integration, no Directive Drafter layer (recommended/default).
- `open_webui_pipe_with_directive_drafter.py`: optional/experimental Directive Drafter layer (heuristic check first, then optional model fallback) before `engine.step(...)`.

## Setup

Quick start for the base pipe:

1. Import `open_webui_pipe.py` as a Function by URL.
2. Enable the function.
3. Set `BASE_MODEL_ID` to a valid Open WebUI model id.
4. Turn on `SHOW_CONTEXT_COMPILER_TRACE=true` if you want easy in-chat verification.
5. Select the pipe model in chat.

Open WebUI is a separate runtime and must already be installed/configured separately.
Open WebUI also needs at least one real backend model/provider configured (for example Ollama or OpenAI) so `BASE_MODEL_ID` resolves to an actual model.
Note: The `PROVIDER` environment contract used in LiteLLM examples/demos does not apply to OpenWebUI. OpenWebUI manages providers via its own connection settings and model IDs.

These examples require `context-compiler>=0.8.3`.

### Configuration

- Open: `http://localhost:3000/admin/functions`
- Verify `BASE_MODEL_ID` matches an existing Open WebUI model id exactly
- Example: `BASE_MODEL_ID = llama3.1:8b`
- Model ids are configured in: `Admin Panel → Settings → Models`

If using `open_webui_pipe_with_directive_drafter.py`:

- Install directive-drafter support if needed:
  `pip install "context-compiler>=0.8.3" "context-compiler-directive-drafter>=0.1.2"`
- Set `PREPROCESSOR_PROMPT_PROFILE=default` for heuristic-first behavior
- Optionally set `PREPROCESSOR_MODEL_ID` to use a separate fallback drafting model
- If `PREPROCESSOR_MODEL_ID` is unset, fallback uses `BASE_MODEL_ID`
- Use `llama` only for LLM-only fallback drafting with Llama-family models

Model fallback output is structurally validated before handoff. This does not prove that the model interpreted the user correctly. The automated fallback path is experimental pending a separate source-aware acceptance policy and reviewed drafting workflow.

### Docker/manual install fallback

If frontmatter dependency installs are disabled, offline, or unavailable:

1. Open a shell in the Open WebUI container:
   - `docker exec -it <openwebui-container> sh`

1. Install the package manually:

- Minimal pipe: `pip install "context-compiler>=0.8.3"`
- Directive Drafter pipe: `pip install "context-compiler>=0.8.3" "context-compiler-directive-drafter>=0.1.2"`

1. Import and enable the function in Open WebUI, then configure valves.

### Finding valid model ids

Use the Open WebUI model picker/list to copy exact model ids for `BASE_MODEL_ID`
(and optional `PREPROCESSOR_MODEL_ID` for the directive-drafter pipe).

## Verify behavior

### Before you start

Use a real Open WebUI runtime that you control locally.

Use a backend model/provider that you can observe during verification.
A local backend or request-capturing proxy is recommended because it makes
it easier to confirm when model calls occur.

For the easiest verification, enable `SHOW_CONTEXT_COMPILER_TRACE=true` in the
function valves before testing. The trace is appended to normal responses and
gives a quick view of what happened on each turn.

If you also have a local proxy or stub that records backend requests, you can
use that as an optional advanced check to confirm the exact forwarded
`[[cc_state]]` system message.

### Base pipe

Use this pipe when you want the simplest Open WebUI integration path.

Suggested verification:

- Send `use docker` and confirm you get `State updated: Use docker.` with trace showing a local turn
- Send a normal prompt such as `what should I run?` and confirm trace shows a forwarded turn with compiler state included
- Send `use docker`, then `prohibit docker`, and confirm Open WebUI rejects the second request instead of changing state
- Optionally send `show state` and confirm the state summary is returned locally

Advanced check:

- If you have a local proxy or stub, inspect the forwarded request and confirm it contains exactly one `[[cc_state]]` system message.
- Confirm that saved premise appears as `Premise: ...` and saved policy appears as `Use: ...` or `Prohibit: ...`.

### Directive-drafter pipe

Use this pipe when you want the same runtime behavior plus Directive Drafter preprocessing.

Suggested verification:

- Send `use docker` and confirm you get `State updated: Use docker.` with trace showing a local turn
- Send `set premise to concise replies` and confirm Open WebUI rejects the request with `Use 'set premise <value>'.`
- Send `please use docker` and confirm either:
  - the Directive Drafter converts it into a local state update, or
  - trace shows the turn followed the normal compiler path without a silent state change
- Send `please use docker`, then `prohibit docker`, and confirm the second request is rejected without creating resumable state
- Send `use docker and prohibit peanuts` and confirm the pipe responds locally that multiple directives are not supported and must be submitted separately
- Send a normal prompt such as `what should I run?` and confirm trace shows a forwarded turn with compiler state included

Advanced check:

- If you have a local proxy or stub, inspect the forwarded request and confirm it contains exactly one `[[cc_state]]` system message reflecting the active state.
- Confirm that saved premise appears as `Premise: ...` and saved policy appears as `Use: ...` or `Prohibit: ...`.

### Optional extra checks

If you want a slightly broader manual pass:

- verify chat isolation with separate real chat ids
- verify state is lost after restart because these examples do not use external persistence
- verify non-text input is bypassed

### Notes

- Trace is the easiest way to verify behavior from the Open WebUI chat output.
- Forwarded-request inspection is optional and most useful when you already have a local proxy or stub.
- Exact `show state` is a local-state check and does not rely on trace output.

## Limits

- No durable external persistence
- No multi-worker or cross-process guarantees
- No Redis, DB, or external storage for checkpoints
- No Filters or Pipelines
- No production hardening

## Behavioral comparisons

### Case 1

- prompt(s): `clear state` → `change premise to formal tone`
- base model: “To adjust the tone… provide the original content…”
- basic pipe: `No premise exists yet. Use 'set premise ...' first.`
- directive-drafter pipe: `No premise exists yet. Use 'set premise ...' first.`
- why this matters: lifecycle rule is enforced in a fixed, repeatable way; base model drifts into generic rewriting help.

### Case 2

- prompt(s): `clear state` → `use docker` → `prohibit docker`
- base model: generic Docker/prohibition guidance text
- basic pipe: `'docker' is already in use. Only one policy per item is allowed. Use 'reset policies' to change it.`
- directive-drafter pipe: same deterministic rejection
- why this matters: the app rejects conflicting changes instead of creating a resumable flow.

### Case 3

- prompt(s): `clear state` → `use podman instead of docker`
- base model: generic “how to switch to Podman” tutorial
- basic pipe: `No exact policy found for "docker". Replacement requires an exact policy match...`
- directive-drafter pipe: same deterministic rejection
- why this matters: the app only replaces a policy when the old item already exists.

### Case 4

- prompt(s): `clear state` → `set premise to concise replies`
- base model: accepts conversational style phrasing
- basic pipe: `Did you mean 'set premise concise replies'?`
- directive-drafter pipe: same deterministic rejection (near-miss is not rewritten)
- why this matters: near-miss text is not silently rewritten.

### Case 5

- prompt(s): `clear state` → `change premise concise replies`
- base model: generic “please revise the request” response
- basic pipe: `Did you mean 'change premise to concise replies'?`
- directive-drafter pipe: same deterministic rejection (near-miss is passed through unchanged)
- why this matters: the app waits for explicit, valid directive text before changing state.

## Compatibility

Tested target: Open WebUI `v0.8.12`.
Validated at runtime on stock Docker Open WebUI with a real backend model provider.

Compatibility note: OpenWebUI `0.9.x` changed `Users.get_user_by_id` to async.
These examples support both sync (`0.8.x`) and async (`0.9.x`) user lookup.

## Troubleshooting

- `BASE_MODEL_ID is required`: set a valid Open WebUI model id in the function valves, or enable `ALLOW_MISSING_BASE_MODEL_FOR_DEBUG=true` only for local testing.
- `BASE_MODEL_ID was not found in Open WebUI models`: copy the exact id from `Admin Panel → Settings → Models`.
- `PREPROCESSOR_MODEL_ID was not found in Open WebUI models`: set a valid fallback model id or leave it unset to default to `BASE_MODEL_ID`.
- `PREPROCESSOR_MODEL_ID must not match the selected pipe model id`: choose a real backend model id, not the pipe model id itself.
- `PREPROCESSOR_MODEL_ID is invalid or not configured in Open WebUI`: the fallback route hit a missing model; fix the configured fallback model or unset it to reuse `BASE_MODEL_ID`.
- `ALLOW_MISSING_BASE_MODEL_FOR_DEBUG=true`: directive-only updates still run locally, but passthrough returns a deterministic debug message instead of calling a downstream model.
- imports fail after function upload: install `context-compiler>=0.8.3` in the Open WebUI runtime, and add `context-compiler-directive-drafter>=0.1.2` only for the Directive Drafter pipe, because the copied function runs from a temp/cached location.

## Fallback notes

- Fallback drafting uses `PREPROCESSOR_MODEL_ID` first, while the main passthrough path still forwards with `BASE_MODEL_ID`.
- If the fallback model returns `model not found`, the pipe normalizes that into the deterministic `PREPROCESSOR_MODEL_ID` misconfiguration message above.
