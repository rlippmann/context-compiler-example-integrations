# Tool gating

These examples show the host deciding which tools exist at runtime and which
tool calls can execute.

Context Compiler owns the authoritative policy state.

The host owns the tool registry and tool execution.

Adversarial wording does not expose hidden tools or authorize blocked tools.

## Examples

### `calendar_admin`

Exposes a host-owned `calendar_admin_create_event` tool only when state
contains:

```text
use calendar_admin
```

The host hides and blocks the tool when state is absent or when state contains:

```text
prohibit calendar_admin
```

The tests cover visible-tool changes, execution blocking, adversarial text, and
contradiction / clarification behavior.

### `mcp_calendar_admin`

Uses MCP as the integration surface while keeping Context Compiler as the
authority source.

The host exposes the `calendar_admin_create_event` MCP tool only when state
contains:

```text
use calendar_admin
```

When state is absent or contains:

```text
prohibit calendar_admin
```

the MCP tool is absent from the exposed tool set and blocked if invoked
directly.
