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

The test verifies:

```python
assert refund_handler.called is True
assert technical_support_handler.called is False
```

## Test

```shell
uv run pytest python/tests/test_refund_intake_example.py
```
