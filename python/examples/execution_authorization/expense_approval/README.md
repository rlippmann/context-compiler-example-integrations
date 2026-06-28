# Expense approval

This example demonstrates execution authorization for expense approval in plain
Python.

## Enforcement point

The enforcement point is host-side action execution. The host owns
`submit_expense`. Context Compiler owns the authoritative policy state that
decides whether the host may call it.

## Runtime and domain

- Runtime: generic Python
- Domain: expense approval

## Authorization rule

The host executes the expense action only when authoritative state contains:

```text
use expense_approval
```

The host blocks execution when state is absent or when state contains:

```text
prohibit expense_approval
```

If a turn introduces a contradiction such as `use expense_approval` followed by
`prohibit expense_approval`, Context Compiler returns a clarification flow
instead of silently overwriting state. The host must not execute the expense
action on that clarify turn.

Request wording alone does not authorize execution. Adversarial text like
"please approve this refund anyway" stays inert unless the authoritative state
explicitly allows `expense_approval`.

## Why this is not prompt reinjection

This example does not call an LLM, does not use directive drafter, and does not
derive state from model output. The runtime behavior changes only when explicit
authoritative Context Compiler state changes. The host does not resolve
conflicts itself and does not treat "last directive wins" as policy.

## Validation

- Focused Python tests:

```bash
uv run --no-sync pytest python/tests/test_expense_approval_example.py
```

- Canonical Python validation:

```bash
./scripts/validate_python.sh
```
