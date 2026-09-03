# Provider Contract

This document is the shared provider contract used by live-model examples in
this repository.

Required (normal `openai` mode):

```shell
export OPENAI_API_KEY=...
```

Optional:

```shell
export PROVIDER=openai
export MODEL=openai/gpt-4o-mini
export DRAFTER_MODEL=openai/gpt-4o-mini
export OPENAI_BASE_URL=...
```

Provider mode contract (`PROVIDER`) is strict:

- `openai`
- `ollama`
- `openai_compatible`

Unknown values hard fail with a validation error.

Resolution precedence:

1. `OPENAI_BASE_URL` override
2. `PROVIDER`
3. default (`openai`)

Operational behavior by mode:

- `openai`
  - default `base_url`: `https://api.openai.com/v1`
  - requires `OPENAI_API_KEY`
- `ollama`
  - default `base_url`: `http://localhost:11434`
  - API key optional
- `openai_compatible`
  - requires `OPENAI_BASE_URL` when explicitly selected with `PROVIDER`
  - API key requirement depends on endpoint

Startup emits one concise config line showing resolved `mode`, `base_url`,
`model`, and resolution `source` (`default`, `PROVIDER`, or
`OPENAI_BASE_URL override`).

`MODEL` and `DRAFTER_MODEL` use LiteLLM format: `<provider>/<model>`.
`DRAFTER_MODEL` is optional and defaults to `MODEL`. `PREPROCESSOR_MODEL` is
deprecated but remains supported as a compatibility alias; `DRAFTER_MODEL`
wins when both are set.

The directive-drafter integration always uses heuristic-first processing with
the configured fallback model when needed.
