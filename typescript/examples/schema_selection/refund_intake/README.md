# Refund intake

This example routes a request to the refund workflow.

The host reads Context Compiler authoritative state and chooses the workflow.

In this example, the host routes the request to the refund workflow because the
authoritative state contains:

```text
use refund_intake
```

The technical-support workflow is available, but it is not used.

Context Compiler does not choose the workflow by prompt wording. The host reads
the saved authoritative state and selects the workflow/schema from that state.

## Enforcement point

Schema selection

## State mechanism

`use`

## What changes

Without matching state, no workflow is selected.

With:

```text
use refund_intake
```

the refund workflow runs.

## Proof

The tests verify:

```ts
assert.equal(selectedSchema, "refund_intake");
assert.equal(refundHandler.called, true);
assert.equal(technicalSupportHandler.called, false);
```

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
