"""Host-side tool gating using authoritative Context Compiler state."""

from dataclasses import dataclass
from typing import Literal, TypedDict, cast

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
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    execution_result: CalendarToolExecutionResult


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
class CalendarAdminHost:
    """Host-owned tool registry and execution layer."""

    execution_log: list[str]

    def __init__(self) -> None:
        self.execution_log = []
        self._always_available_tools = ["calendar_view_events"]
        self._calendar_admin_tools = ["calendar_admin_create_event"]

    def visible_tools(self, state: State) -> ToolRegistrySnapshot:
        available_tools = self._always_available_tools.copy()
        hidden_tools = self._calendar_admin_tools.copy()

        if calendar_admin_tools_are_allowed(state):
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


def calendar_admin_tools_are_allowed(state: State) -> bool:
    """Allow calendar admin tools only from authoritative compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))

    if "calendar_admin" in prohibit_items:
        return False

    return "calendar_admin" in use_items


def execute_calendar_admin_tool_if_allowed(
    tool_call: CalendarToolCall,
    *,
    state: State,
    host: CalendarAdminHost,
) -> CalendarToolExecutionResult:
    """Hide or execute the admin tool based only on authoritative state."""

    registry_snapshot = host.visible_tools(state)
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
    """Block tool exposure on clarify and otherwise enforce current state."""

    decision = engine.step(compiler_input)

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "execution_result": {
                "authorization_state": "blocked",
                "tool_visible": False,
                "executed": False,
                "blocked_reason": "clarification required before exposing calendar admin tools",
                "tool_result": None,
                "registry_snapshot": host.visible_tools(engine.state),
                "execution_log": host.execution_log.copy(),
            },
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "execution_result": execute_calendar_admin_tool_if_allowed(
            tool_call,
            state=authoritative_state,
            host=host,
        ),
    }


def run_demo() -> CalendarToolExecutionResult:
    """Run a deterministic demonstration with explicit authorization state."""

    engine = create_engine()
    engine.step("use calendar_admin")
    host = CalendarAdminHost()

    return execute_calendar_admin_tool_if_allowed(
        {
            "tool_name": "calendar_admin_create_event",
            "calendar_id": "ops-admin",
            "event_title": "Quarterly access review",
        },
        state=engine.state,
        host=host,
    )
