# Schema selection

These examples show how authoritative state changes which host-side path runs.

They demonstrate observable runtime behavior changes rather than model
compliance.

## Examples

### `refund_intake`

Shows two generic schema-selection mechanisms in the same customer
order/support intake domain.

Policy-driven selection can route requests when state contains:

```text
use refund_intake
```

Premise-driven selection can also change schema choice for the same ambiguous
request when saved factual order context changes.

This example keeps premise factual. It does not treat premise as a disguised
workflow command.

### `vercel_ai_sdk_generate_object`

Shows a host selecting a structured-output schema from compiled policy state.
The provider-free tests are canonical, and the example also offers an opt-in
live-model validation through Vercel AI SDK `generateObject`.

## Technology-specific examples

The generic examples teach the enforcement point first.

Concrete runtime surfaces currently linked from this repo:

- [typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/examples/schema_selection/vercel_ai_sdk_generate_object/README.md)
- [python/examples/schema_selection/ollama_structured_output/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/schema_selection/ollama_structured_output/README.md)
- `python/examples/schema_selection/litellm_response_format/response_format.py`
