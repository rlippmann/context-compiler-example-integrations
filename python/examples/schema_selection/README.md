# Schema selection

These examples show how authoritative state changes which host-side path runs.

They demonstrate observable runtime behavior changes rather than model compliance.

## Examples

### `refund_intake`

Routes requests to a refund workflow when state contains:

```text
use refund_intake
```

The test verifies that the refund handler runs and the technical-support
handler does not.

### `ollama_structured_output`

Shows a host selecting an Ollama `format` schema from compiled policy state.

### `litellm_response_format`

Shows a host selecting a LiteLLM `response_format` from compiled policy state.

## Technology-specific examples

The generic examples teach the enforcement point first.

Concrete runtime surfaces currently linked from this repo:

- [python/examples/schema_selection/ollama_structured_output/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/schema_selection/ollama_structured_output/README.md)
- `python/examples/schema_selection/litellm_response_format/response_format.py`
- [typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md)
