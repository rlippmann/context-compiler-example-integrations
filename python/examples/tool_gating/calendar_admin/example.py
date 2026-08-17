"""Host-side tool gating using authoritative Context Compiler state."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypedDict

from context_compiler import (
    Decision,
    DecisionKind,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    Engine,
)


class CalendarToolCall(TypedDict):
    tool_name: str
    calendar_id: str
    event_title: str


class ToolRegistrySnapshot(TypedDict):
    available_tools: list[str]
    hidden_tools: list[str]


class CalendarToolExecutionResult(TypedDict):
    authorization_state: Literal["allowed", "blocked"]
    tool_visible: bool
    executed: bool
    blocked_reason: str | None
    tool_result: str | None
    registry_snapshot: ToolRegistrySnapshot
    execution_log: list[str]


class CalendarToolTurnResult(TypedDict):
    decision_kind: Literal["error", "update", "passthrough"]
    prompt_to_user: str | None
    execution_result: CalendarToolExecutionResult


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
class CalendarAdminHost:
    """Host-owned tool registry and execution layer."""

    execution_log: list[str]

    def __init__(self) -> None:
        self.execution_log = []
        self._always_available_tools = ["calendar_view_events"]
        self._calendar_admin_tools = ["calendar_admin_create_event"]

    def visible_tools(
        self, policies: Mapping[str, PolicyValue]
    ) -> ToolRegistrySnapshot:
        available_tools = self._always_available_tools.copy()
        hidden_tools = self._calendar_admin_tools.copy()

        if calendar_admin_tools_are_allowed(policies):
            available_tools.extend(self._calendar_admin_tools)
            hidden_tools = []

        return {
            "available_tools": available_tools,
            "hidden_tools": hidden_tools,
        }

    def execute_calendar_admin_tool(self, tool_call: CalendarToolCall) -> str:
        self.execution_log.append(
            f"{tool_call['tool_name']}:{tool_call['calendar_id']}:{tool_call['event_title']}"
        )
        return (
            f"created event '{tool_call['event_title']}' "
            f"on calendar '{tool_call['calendar_id']}'"
        )


def calendar_admin_tools_are_allowed(policies: Mapping[str, PolicyValue]) -> bool:
    """Allow calendar admin tools only from authoritative compiler state."""

    if policies.get("calendar_admin") == POLICY_PROHIBIT:
        return False

    return policies.get("calendar_admin") == POLICY_USE


def execute_calendar_admin_tool_if_allowed(
    tool_call: CalendarToolCall,
    *,
    policies: Mapping[str, PolicyValue],
    host: CalendarAdminHost,
) -> CalendarToolExecutionResult:
    """Hide or execute the admin tool based only on authoritative state."""

    registry_snapshot = host.visible_tools(policies)
    tool_visible = tool_call["tool_name"] in registry_snapshot["available_tools"]

    if not tool_visible:
        return {
            "authorization_state": "blocked",
            "tool_visible": False,
            "executed": False,
            "blocked_reason": "calendar_admin state not authorized",
            "tool_result": None,
            "registry_snapshot": registry_snapshot,
            "execution_log": host.execution_log.copy(),
        }

    tool_result = host.execute_calendar_admin_tool(tool_call)
    return {
        "authorization_state": "allowed",
        "tool_visible": True,
        "executed": True,
        "blocked_reason": None,
        "tool_result": tool_result,
        "registry_snapshot": registry_snapshot,
        "execution_log": host.execution_log.copy(),
    }


def handle_calendar_admin_turn(
    engine: Engine,
    *,
    compiler_input: str,
    tool_call: CalendarToolCall,
    host: CalendarAdminHost,
) -> CalendarToolTurnResult:
    """Block tool exposure on compiler rejection and otherwise enforce state."""

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
                "blocked_reason": "compiler rejected calendar admin state change",
                "tool_result": None,
                "registry_snapshot": host.visible_tools(engine.policies),
                "execution_log": host.execution_log.copy(),
            },
        }

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.message
        if decision.kind == DecisionKind.ERROR
        else None,
        "execution_result": execute_calendar_admin_tool_if_allowed(
            tool_call,
            policies=engine.policies,
            host=host,
        ),
    }


def run_demo() -> CalendarToolExecutionResult:
    """Run a deterministic demonstration with explicit authorization state."""

    engine = Engine()
    engine.step("use calendar_admin")
    host = CalendarAdminHost()

    return execute_calendar_admin_tool_if_allowed(
        {
            "tool_name": "calendar_admin_create_event",
            "calendar_id": "ops-admin",
            "event_title": "Quarterly access review",
        },
        policies=engine.policies,
        host=host,
    )
