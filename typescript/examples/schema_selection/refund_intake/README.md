# Refund intake

This example shows two host-side schema-selection mechanisms in the same
customer order/support intake domain.

The host reads Context Compiler authoritative state and chooses the workflow.

The enforcement point stays the same:

- same user request
- different authoritative state
- different host-selected schema

Context Compiler does not choose the workflow by prompt wording. The host reads
the saved authoritative state and selects the workflow/schema from that state.
For premise-driven selection, the host applies a small deterministic
order-intake rule:

`saved order facts -> intake category -> selected schema`

In this example, the host checks for a few explicit order facts in the saved
premise, such as `delivered physical item` plus `damaged on arrival`, or
`digital subscription` plus `login failure`.

## Enforcement point

Schema selection

## State mechanisms

- policy-driven schema selection via `use ...`
- premise-driven schema selection via factual order context

## What changes

Without matching authoritative state, no workflow is selected.

With policy state:

```text
use refund_intake
```

the refund workflow runs.

With a factual premise:

```text
set premise order A-100 is a delivered physical item reported as damaged on arrival
```

the same ambiguous user request, `I need help with order A-100.`, selects the
`refund_intake` schema.

In the host rule layer, that saved premise maps to the
`damaged_physical_delivery` intake category, which then maps to
`refund_intake`.

With a different factual premise:

```text
set premise order A-100 is a digital subscription with an active login failure after purchase
```

the same ambiguous user request selects the `technical_support` schema.

In the host rule layer, that saved premise maps to the
`digital_subscription_login_failure` intake category, which then maps to
`technical_support`.

The premise is factual context about the order. It is not a workflow command
and it is not rewritten as `use refund_intake` or `use technical_support`.
This mapping is host-owned business logic, not model inference.

## Proof

The tests verify:

```ts
assert.equal(selectedSchema, "refund_intake");
assert.equal(refundHandler.called, true);
assert.equal(technicalSupportHandler.called, false);
```

They also verify:

- `use refund_intake` selects `refund_intake`
- `use technical_support` selects `technical_support`
- saved premise facts map to a named intake category before schema selection
- the same request plus different saved premise selects different schemas
- unrelated premise selects no schema
- adversarial user text does not override saved policy or saved premise

## Install

```shell
cd typescript/examples/schema_selection/refund_intake
npm install
```

## Validate

```shell
cd typescript/examples/schema_selection/refund_intake
npm run build
npm run typecheck
npm test
```
