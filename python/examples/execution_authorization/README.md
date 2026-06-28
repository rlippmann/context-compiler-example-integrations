# Execution authorization

These examples show host-side actions executing only when authoritative Context
Compiler state explicitly authorizes them.

They demonstrate observable runtime behavior changes rather than prompt
compliance. User wording alone does not authorize the action.

## Examples

### `expense_approval`

Authorizes a host-owned `submit_expense` function only when state contains:

```text
use expense_approval
```

The host blocks execution when state is absent or when state contains:

```text
prohibit expense_approval
```

The tests cover authorized execution, absent-state blocking, prohibited-state
blocking, adversarial request text, and the runtime behavior change between
blocked and authorized state.
