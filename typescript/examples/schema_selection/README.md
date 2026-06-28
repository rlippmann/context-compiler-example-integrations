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
