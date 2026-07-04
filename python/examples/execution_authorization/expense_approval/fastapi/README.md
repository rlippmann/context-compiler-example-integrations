# Model approval is not authorization

This FastAPI variant provides provider-free runtime-boundary validation by
default, plus an opt-in live-model validation path.

Tier 2 already proves deterministic enforcement against local and adversarial
stubs.

The default tests here prove the runtime boundary behavior with a visible
approval-class claim present at the request surface.

If you also run the opt-in live-model validation with
`RUN_EXPENSE_APPROVAL_LIVE_MODEL=1`, this variant demonstrates that the same
boundary still matters when a real model says the expense is approved.

## What the user sees

The app exposes two mutation paths for the same expense request:

- baseline path: a naive host trusts the model approval claim and executes the
  protected mutation
- compiler-mediated path: the host sees the same kind of model approval claim,
  but only executes when authoritative Context Compiler state permits
  `expense_approval`

The request also carries a visible `agent_claim` field to represent
caller-supplied or model-supplied approval text.

The observable proof is a host-owned append-only JSONL file:

- baseline writes one record when the model returns an approval-class claim
- compiler-mediated returns `403` and writes no record when state does not
  authorize execution
- compiler-mediated writes one record only when authoritative state includes:

```text
use expense_approval
```

If a request introduces a contradiction such as `prohibit expense_approval`
against an already authorized state, Context Compiler returns a clarify flow.
The host returns a conflict response and writes no record.

## Same request, different state

The compiler-mediated proof uses the same endpoint, the same approval-class
model claim, and the same expense action. Only authoritative Context Compiler
state changes.

| Endpoint | Model claim | Authoritative state | Compiler input | Outcome |
| --- | --- | --- | --- | --- |
| `/compiler/expenses` | approved | absent | none | `403`, no side effect |
| `/compiler/expenses` | approved | `use expense_approval` | none | `200`, one side effect |
| `/compiler/expenses` | approved | `use expense_approval` | `prohibit expense_approval` | `409`, clarify, no new side effect |

## Enforcement boundary

The model claim is visible in both paths.

Caller-supplied approval text is also visible in both paths.

The baseline host treats that claim as authority.

The compiler-mediated host does not treat the visible approval text as
authorization.

Context Compiler state is the only authorization source for the protected
mutation after an approval-class claim is present in the compiler-mediated path.

## Validation

Focused provider-free tests:

```bash
uv run --no-sync pytest python/tests/test_fastapi_expense_approval_example.py
```

Optional live-model validation:

```bash
export RUN_EXPENSE_APPROVAL_LIVE_MODEL=1
export OPENAI_API_KEY=...
export MODEL=openai/gpt-4o-mini
uv run --no-sync pytest python/tests/test_fastapi_expense_approval_live_model.py
```

Unless you run that env-var-gated command, this repo has only validated the
provider-free runtime-boundary path, not the live-provider path.

The live-model path uses the same shared provider contract already used
elsewhere in this repo:

- `PROVIDER`
- `MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

## Run locally

```bash
uv run fastapi dev python/examples/execution_authorization/expense_approval/fastapi/app.py
```
