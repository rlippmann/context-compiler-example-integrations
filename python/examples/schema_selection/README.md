# Schema selection

These examples show how authoritative state changes which host-side path runs.

They demonstrate observable runtime behavior changes rather than model compliance.

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

### `ollama_structured_output`

Shows a host selecting an Ollama `format` schema from compiled policy state.

### `litellm_response_format`

Shows a host selecting a LiteLLM `response_format` from compiled policy state.

## Technology-specific examples

The generic examples teach the enforcement point first.

Concrete runtime surfaces currently linked from this repo:

- [python/examples/schema_selection/ollama_structured_output/README.md](ollama_structured_output/README.md)
- `python/examples/schema_selection/litellm_response_format/response_format.py`
