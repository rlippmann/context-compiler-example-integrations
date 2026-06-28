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
