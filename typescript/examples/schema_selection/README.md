# Schema selection

These examples show how authoritative state changes which host-side path runs.

They demonstrate observable runtime behavior changes rather than model
compliance.

## Examples

### `refund_intake`

Routes requests to a refund workflow when state contains:

```text
use refund_intake
```

The tests verify that the refund handler runs only when authoritative state
selects it.

### `vercel_ai_sdk_generate_object`

Shows a host selecting a structured-output schema from compiled policy state.

## Technology-specific examples

The generic examples teach the enforcement point first.

Concrete runtime surfaces currently linked from this repo:

- [typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md)
- [python/examples/schema_selection/ollama_structured_output/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/schema_selection/ollama_structured_output/README.md)
- `python/examples/schema_selection/litellm_response_format/response_format.py`
