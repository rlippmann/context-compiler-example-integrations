"""MCP-surface tool gating using authoritative Context Compiler state."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict

from context_compiler import (
    Decision,
    DecisionKind,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    Engine,
)


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
    decision_kind: Literal["error", "update", "passthrough"]
    prompt_to_user: str | None
    execution_result: McpToolExecutionResult


class McpDecisionResult(TypedDict):
    decision_kind: Literal["error", "update", "passthrough"]
    prompt_to_user: str | None
    exposed_tools: ExposedMcpTools
    execution_result: NotRequired[McpToolExecutionResult]


def _decision_kind_name(
    decision: Decision,
) -> Literal["error", "update", "passthrough"]:
    kind = decision.kind
    if kind == DecisionKind.ERROR:
        return "error"
    if kind == DecisionKind.UPDATE:
        return "update"
    if kind == DecisionKind.NO_DIRECTIVE:
        return "passthrough"
    raise ValueError(f"unexpected decision kind: {kind}")


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

    def exposed_mcp_tools(self, policies: Mapping[str, PolicyValue]) -> ExposedMcpTools:
        tools = self._always_available_tools.copy()
        hidden_tool_names = [tool["name"] for tool in self._calendar_admin_tools]

        if calendar_admin_mcp_tools_are_allowed(policies):
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


def calendar_admin_mcp_tools_are_allowed(policies: Mapping[str, PolicyValue]) -> bool:
    """Allow admin MCP tools only from authoritative compiler state."""

    if policies.get("calendar_admin") == POLICY_PROHIBIT:
        return False

    return policies.get("calendar_admin") == POLICY_USE


def execute_mcp_tool_if_allowed(
    tool_call: McpToolCall,
    *,
    policies: Mapping[str, PolicyValue],
    host: CalendarAdminMcpHost,
) -> McpToolExecutionResult:
    """Expose and execute MCP tools only when authoritative state allows them."""

    exposed_tools = host.exposed_mcp_tools(policies)
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
    """Block MCP tool exposure on compiler rejection and otherwise enforce state."""

    decision = engine.step(compiler_input)

    if decision.kind == DecisionKind.ERROR:
        return {
            "decision_kind": "error",
            "prompt_to_user": decision.message
            if decision.kind == DecisionKind.ERROR
            else None,
            "execution_result": {
                "authorization_state": "blocked",
                "tool_visible": False,
                "executed": False,
                "blocked_reason": "compiler rejected calendar admin MCP state change",
                "tool_result": None,
                "exposed_tools": host.exposed_mcp_tools(engine.policies),
                "execution_log": host.execution_log.copy(),
            },
        }

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.message
        if decision.kind == DecisionKind.ERROR
        else None,
        "execution_result": execute_mcp_tool_if_allowed(
            tool_call,
            policies=engine.policies,
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

    if decision.kind == DecisionKind.ERROR:
        return {
            "decision_kind": "error",
            "prompt_to_user": decision.message
            if decision.kind == DecisionKind.ERROR
            else None,
            "exposed_tools": host.exposed_mcp_tools(engine.policies),
        }

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.message
        if decision.kind == DecisionKind.ERROR
        else None,
        "exposed_tools": host.exposed_mcp_tools(engine.policies),
    }


def run_demo() -> McpToolExecutionResult:
    """Run a deterministic MCP demonstration with explicit authorization state."""

    engine = Engine()
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
        policies=engine.policies,
        host=host,
    )
