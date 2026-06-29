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

## Related integrations

The generic examples teach the execution-authorization enforcement point in a
small host-owned flow.

For a small TypeScript host runtime surface, see:

- [typescript/starter_apps/node/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/README.md)
