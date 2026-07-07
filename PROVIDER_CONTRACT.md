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
export PREPROCESSOR_MODEL=openai/gpt-4o-mini
export OPENAI_BASE_URL=...
export PREPROCESSOR_PROMPT_PROFILE=default
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

`MODEL` and `PREPROCESSOR_MODEL` use LiteLLM format: `<provider>/<model>`.
`PREPROCESSOR_MODEL` is optional and defaults to `MODEL`.

For heuristic-first usage, keep `PREPROCESSOR_PROMPT_PROFILE=default`.
Use `llama` only for LLM-only preprocessing with Llama-family models.
