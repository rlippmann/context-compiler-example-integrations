# Customer support routing

This example demonstrates a host-owned gateway enforcing authoritative
Context Compiler state before a downstream support handler runs.

The gateway reads authoritative state and decides whether a request that asks
for `billing_support` may cross the middleware boundary.

The downstream support service is called only after the gateway allows the
request.

## Policy mapping

The gateway routes a billing request to `billing_support` only when state
contains:

```text
use billing_support
```

If state is absent, the gateway blocks billing requests.

If state contains:

```text
prohibit billing_support
```

the gateway also blocks billing requests.

Requests that are not asking for billing support follow the host's documented
default path, `general_support`.

## What this example demonstrates

- Context Compiler owns authoritative policy state.
- The host owns the gateway middleware boundary and the downstream call.
- Adversarial request text does not bypass the gateway decision.
- Contradictory `use billing_support` and `prohibit billing_support` inputs
  produce clarification behavior instead of a silent overwrite.
- The example does not call an LLM, does not use directive drafter, and does
  not derive state from model output.
