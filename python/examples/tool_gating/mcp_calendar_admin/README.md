# `mcp_calendar_admin`

This example shows tool gating where MCP is the integration surface and the
host owns the MCP registry plus MCP tool execution.

Context Compiler owns the authoritative policy state that decides whether the
host exposes the calendar admin MCP tool.

The host exposes and allows `calendar_admin_create_event` only when state
contains:

```text
use calendar_admin
```

The host omits that tool from the exposed MCP tool set when state is absent or
when state contains:

```text
prohibit calendar_admin
```

If a caller still invokes the hidden tool directly, the host blocks execution.

Adversarial request text does not expose the tool or mutate policy state.
