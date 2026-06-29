"""MCP-surface tool gating using authoritative Context Compiler state."""

from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict, cast

from context_compiler import (
    POLICY_PROHIBIT,
    POLICY_USE,
    State,
    create_engine,
    get_decision_state,
    get_policy_items,
    is_clarify,
)
from context_compiler.engine import Engine


class McpToolDefinition(TypedDict):
    name: str
    title: str
    description: str


class McpToolCall(TypedDict):
    tool_name: str
    arguments: dict[str, str]


class ExposedMcpTools(TypedDict):
    tools: list[McpToolDefinition]
    hidden_tool_names: list[str]


class McpToolExecutionResult(TypedDict):
    authorization_state: Literal["allowed", "blocked"]
    tool_visible: bool
    executed: bool
    blocked_reason: str | None
    tool_result: str | None
    exposed_tools: ExposedMcpTools
    execution_log: list[str]


class McpToolTurnResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    execution_result: McpToolExecutionResult


class McpDecisionResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    exposed_tools: ExposedMcpTools
    execution_result: NotRequired[McpToolExecutionResult]


def _decision_kind_name(
    decision: object,
) -> Literal["clarify", "update", "passthrough"]:
    if not isinstance(decision, dict):
        raise ValueError("unexpected decision shape")

    kind = decision.get("kind")
    kind_name = getattr(kind, "value", None)
    if kind_name not in {"clarify", "update", "passthrough"}:
        raise ValueError(f"unexpected decision kind: {kind_name}")

    return cast(Literal["clarify", "update", "passthrough"], kind_name)


@dataclass
class CalendarAdminMcpHost:
    """Host-owned MCP registry and execution layer."""

    execution_log: list[str] = field(default_factory=list)
    _always_available_tools: list[McpToolDefinition] = field(
        default_factory=lambda: [
            {
                "name": "calendar_view_events",
                "title": "View calendar events",
                "description": "List visible events from a calendar.",
            }
        ]
    )
    _calendar_admin_tools: list[McpToolDefinition] = field(
        default_factory=lambda: [
            {
                "name": "calendar_admin_create_event",
                "title": "Create calendar event",
                "description": "Create an administrative event on a calendar.",
            }
        ]
    )

    def exposed_mcp_tools(self, state: State) -> ExposedMcpTools:
        tools = self._always_available_tools.copy()
        hidden_tool_names = [tool["name"] for tool in self._calendar_admin_tools]

        if calendar_admin_mcp_tools_are_allowed(state):
            tools.extend(self._calendar_admin_tools)
            hidden_tool_names = []

        return {
            "tools": tools,
            "hidden_tool_names": hidden_tool_names,
        }

    def execute_mcp_tool(self, tool_call: McpToolCall) -> str:
        calendar_id = tool_call["arguments"]["calendar_id"]
        event_title = tool_call["arguments"]["event_title"]
        self.execution_log.append(
            f"{tool_call['tool_name']}:{calendar_id}:{event_title}"
        )
        return f"created event '{event_title}' on calendar '{calendar_id}'"


def calendar_admin_mcp_tools_are_allowed(state: State) -> bool:
    """Allow admin MCP tools only from authoritative compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))

    if "calendar_admin" in prohibit_items:
        return False

    return "calendar_admin" in use_items


def execute_mcp_tool_if_allowed(
    tool_call: McpToolCall,
    *,
    state: State,
    host: CalendarAdminMcpHost,
) -> McpToolExecutionResult:
    """Expose and execute MCP tools only when authoritative state allows them."""

    exposed_tools = host.exposed_mcp_tools(state)
    visible_tool_names = [tool["name"] for tool in exposed_tools["tools"]]
    tool_visible = tool_call["tool_name"] in visible_tool_names

    if not tool_visible:
        return {
            "authorization_state": "blocked",
            "tool_visible": False,
            "executed": False,
            "blocked_reason": "calendar_admin state not authorized",
            "tool_result": None,
            "exposed_tools": exposed_tools,
            "execution_log": host.execution_log.copy(),
        }

    tool_result = host.execute_mcp_tool(tool_call)
    return {
        "authorization_state": "allowed",
        "tool_visible": True,
        "executed": True,
        "blocked_reason": None,
        "tool_result": tool_result,
        "exposed_tools": exposed_tools,
        "execution_log": host.execution_log.copy(),
    }


def handle_mcp_tool_turn(
    engine: Engine,
    *,
    compiler_input: str,
    tool_call: McpToolCall,
    host: CalendarAdminMcpHost,
) -> McpToolTurnResult:
    """Block MCP tool exposure on clarify and otherwise enforce current state."""

    decision = engine.step(compiler_input)

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "execution_result": {
                "authorization_state": "blocked",
                "tool_visible": False,
                "executed": False,
                "blocked_reason": "clarification required before exposing calendar admin MCP tools",
                "tool_result": None,
                "exposed_tools": host.exposed_mcp_tools(engine.state),
                "execution_log": host.execution_log.copy(),
            },
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "execution_result": execute_mcp_tool_if_allowed(
            tool_call,
            state=authoritative_state,
            host=host,
        ),
    }


def describe_exposed_mcp_tools(
    engine: Engine,
    *,
    compiler_input: str,
    host: CalendarAdminMcpHost,
) -> McpDecisionResult:
    """Return the currently exposed MCP tools after applying compiler input."""

    decision = engine.step(compiler_input)

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "exposed_tools": host.exposed_mcp_tools(engine.state),
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "exposed_tools": host.exposed_mcp_tools(authoritative_state),
    }


def run_demo() -> McpToolExecutionResult:
    """Run a deterministic MCP demonstration with explicit authorization state."""

    engine = create_engine()
    engine.step("use calendar_admin")
    host = CalendarAdminMcpHost()

    return execute_mcp_tool_if_allowed(
        {
            "tool_name": "calendar_admin_create_event",
            "arguments": {
                "calendar_id": "ops-admin",
                "event_title": "Quarterly access review",
            },
        },
        state=engine.state,
        host=host,
    )
