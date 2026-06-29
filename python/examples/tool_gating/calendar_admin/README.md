# `calendar_admin`

This example shows host-side tool gating with explicit authoritative Context
Compiler state.

The host owns the tool registry and tool execution.

Context Compiler owns the policy state that decides whether the host exposes
`calendar_admin_create_event`.

The host exposes and allows the calendar admin tool only when state contains:

```text
use calendar_admin
```

The host hides and blocks the calendar admin tool when state is absent or when
state contains:

```text
prohibit calendar_admin
```

Adversarial request text does not enable the tool because the host never derives
authority from user wording or model output.

The tests cover:

- allowed exposure and execution
- absent-state hiding and blocking
- prohibited-state hiding and blocking
- adversarial text that tries to self-authorize
- runtime behavior changing only when authoritative state changes
- contradiction and clarification behavior for conflicting `use` and `prohibit`
