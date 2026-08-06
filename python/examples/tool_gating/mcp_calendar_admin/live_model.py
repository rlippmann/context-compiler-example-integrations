"""Opt-in live-model tool-gating comparison for MCP calendar admin."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal, TypedDict, cast

from context_compiler import (
    DecisionKind,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    create_engine,
)

from context_compiler_example_integrations.examples._shared.litellm_request import (
    build_litellm_provider_kwargs,
)
from context_compiler_example_integrations.examples.tool_gating.mcp_calendar_admin.example import (
    CalendarAdminMcpHost,
    McpToolCall,
)
from context_compiler_example_integrations.examples._shared.provider_mode import (
    print_startup_config,
    resolve_provider_config,
)


class SideEffectRecord(TypedDict):
    tool_name: str
    calendar_id: str
    event_title: str
    authorization_source: Literal["context_compiler_state"]


class LiveModelResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"] | None
    prompt_to_user: str | None
    exposed_tool_names: list[str]
    hidden_tool_names: list[str]
    protected_tool_exposed: bool
    model_selected_tool_name: str | None
    executed: bool
    blocked_reason: str | None
    tool_result: str | None
    execution_log: list[str]
    side_effect_path: str
    side_effect_count: int


class _LiteLLMCallKwargs(TypedDict, total=False):
    model: str
    messages: list[dict[str, str]]
    tools: list[dict[str, object]]
    tool_choice: str
    temperature: float
    drop_params: bool
    api_base: str
    api_key: str


@dataclass(frozen=True)
class _SelectedToolCall:
    name: str | None
    arguments: dict[str, str]


@dataclass
class CalendarAdminSideEffectStore:
    """Host-owned append-only artifact for successful protected execution."""

    artifact_path: Path

    def append(self, *, tool_call: McpToolCall) -> None:
        record: SideEffectRecord = {
            "tool_name": tool_call["tool_name"],
            "calendar_id": tool_call["arguments"]["calendar_id"],
            "event_title": tool_call["arguments"]["event_title"],
            "authorization_source": "context_compiler_state",
        }
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with self.artifact_path.open("a", encoding="utf-8") as artifact:
            artifact.write(json.dumps(record, sort_keys=True) + "\n")

    def count(self) -> int:
        if not self.artifact_path.exists():
            return 0
        with self.artifact_path.open(encoding="utf-8") as artifact:
            return sum(1 for _ in artifact)


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


def _load_authoritative_state(
    authoritative_state: Mapping[str, object] | None,
) -> tuple[str | None, dict[str, PolicyValue]]:
    if authoritative_state is None:
        return None, {}

    premise = authoritative_state.get("premise")
    raw_policies = authoritative_state.get("policies")
    policies: dict[str, PolicyValue] = {}
    if isinstance(raw_policies, Mapping):
        for key, value in raw_policies.items():
            if isinstance(key, str) and value in {POLICY_USE, POLICY_PROHIBIT}:
                policies[key] = cast(PolicyValue, value)
    return premise if isinstance(premise, str) else None, policies


def _decision_kind_name(
    decision: object,
) -> Literal["clarify", "update", "passthrough"]:
    if not isinstance(decision, dict):
        raise ValueError("unexpected decision shape")

    kind = decision.get("kind")
    if kind == DecisionKind.ERROR:
        return "clarify"
    if kind == DecisionKind.UPDATE:
        return "update"
    if kind == DecisionKind.NO_DIRECTIVE:
        return "passthrough"
    raise ValueError(f"unexpected decision kind: {kind}")


def _exposed_tool_names(
    host: CalendarAdminMcpHost, policies: Mapping[str, PolicyValue]
) -> tuple[list[str], list[str]]:
    exposed_tools = host.exposed_mcp_tools(policies)
    return (
        [tool["name"] for tool in exposed_tools["tools"]],
        exposed_tools["hidden_tool_names"],
    )


def _build_openai_tools(
    host: CalendarAdminMcpHost, policies: Mapping[str, PolicyValue]
) -> list[dict[str, object]]:
    exposed_tools = host.exposed_mcp_tools(policies)["tools"]
    tools: list[dict[str, object]] = []
    for tool in exposed_tools:
        if tool["name"] == "calendar_view_events":
            input_schema: dict[str, object] = {
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar identifier to inspect.",
                    }
                },
                "required": ["calendar_id"],
                "additionalProperties": False,
            }
        elif tool["name"] == "calendar_admin_create_event":
            input_schema = {
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Administrative calendar identifier.",
                    },
                    "event_title": {
                        "type": "string",
                        "description": "Administrative event title to create.",
                    },
                },
                "required": ["calendar_id", "event_title"],
                "additionalProperties": False,
            }
        else:
            continue

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": input_schema,
                },
            }
        )
    return tools


def _build_messages(user_intent: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a careful assistant.\n"
                "Use a tool if one is available to complete the user's request.\n"
                "Do not invent unavailable tools."
            ),
        },
        {"role": "user", "content": user_intent},
    ]


def _mapping_value(obj: object, key: str) -> object | None:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_selected_tool_call(response: object) -> _SelectedToolCall:
    choices = _mapping_value(response, "choices")
    if not isinstance(choices, list) or not choices:
        choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return _SelectedToolCall(name=None, arguments={})

    message = _mapping_value(choices[0], "message")
    if message is None:
        return _SelectedToolCall(name=None, arguments={})

    tool_calls = _mapping_value(message, "tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return _SelectedToolCall(name=None, arguments={})

    first_tool_call = tool_calls[0]
    function_payload = _mapping_value(first_tool_call, "function")
    if function_payload is None:
        return _SelectedToolCall(name=None, arguments={})

    name = _mapping_value(function_payload, "name")
    raw_arguments = _mapping_value(function_payload, "arguments")
    if not isinstance(name, str):
        return _SelectedToolCall(name=None, arguments={})

    if isinstance(raw_arguments, str):
        decoded_arguments = json.loads(raw_arguments)
    elif isinstance(raw_arguments, Mapping):
        decoded_arguments = dict(raw_arguments)
    else:
        decoded_arguments = {}

    arguments = {
        key: str(value)
        for key, value in decoded_arguments.items()
        if isinstance(key, str)
    }
    return _SelectedToolCall(name=name, arguments=arguments)


def _call_live_model(
    *, user_intent: str, tools: list[dict[str, object]]
) -> _SelectedToolCall:
    try:
        completion = _get_litellm_completion()
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "litellm is required. Install with: pip install litellm"
        ) from exc

    config = resolve_provider_config(default_model="openai/gpt-4o-mini")
    print_startup_config(config)

    kwargs: _LiteLLMCallKwargs = {
        **build_litellm_provider_kwargs(config),
        "messages": _build_messages(user_intent),
        "tools": tools,
        "tool_choice": "auto",
    }

    response = completion(**kwargs)
    return _extract_selected_tool_call(response)


def run_live_model_turn(
    *,
    user_intent: str,
    authoritative_state: Mapping[str, object] | None = None,
    compiler_input: str = "",
    artifact_path: Path | None = None,
    model_tool_selector: Callable[..., _SelectedToolCall] | None = None,
) -> LiveModelResult:
    """Run one tool-gated turn with a live model or injected selector."""

    if artifact_path is None:
        artifact_path = Path(
            "/tmp/context_compiler_mcp_calendar_admin/tool_calls.jsonl"
        )

    side_effect_store = CalendarAdminSideEffectStore(artifact_path=artifact_path)
    host = CalendarAdminMcpHost()
    engine = create_engine()
    premise, policies = _load_authoritative_state(authoritative_state)
    if authoritative_state is not None:
        engine.import_json(
            json.dumps(
                {
                    "premise": premise,
                    "policies": policies,
                    "version": 2,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    decision_kind: Literal["clarify", "update", "passthrough"] | None = None
    prompt_to_user: str | None = None
    effective_policies = dict(engine.policies)

    if compiler_input:
        decision = engine.step(compiler_input)
        decision_kind = _decision_kind_name(decision)
        prompt_to_user = decision["message"]
        if decision["kind"] == DecisionKind.ERROR:
            exposed_tool_names, hidden_tool_names = _exposed_tool_names(
                host, engine.policies
            )
            return {
                "decision_kind": decision_kind,
                "prompt_to_user": prompt_to_user,
                "exposed_tool_names": exposed_tool_names,
                "hidden_tool_names": hidden_tool_names,
                "protected_tool_exposed": "calendar_admin_create_event"
                in exposed_tool_names,
                "model_selected_tool_name": None,
                "executed": False,
                "blocked_reason": (
                    "clarification required before exposing calendar admin MCP tools"
                ),
                "tool_result": None,
                "execution_log": host.execution_log.copy(),
                "side_effect_path": str(side_effect_store.artifact_path),
                "side_effect_count": side_effect_store.count(),
            }

        effective_policies = dict(engine.policies)

    exposed_tool_names, hidden_tool_names = _exposed_tool_names(
        host, effective_policies
    )
    protected_tool_exposed = "calendar_admin_create_event" in exposed_tool_names
    tools = _build_openai_tools(host, effective_policies)
    selector = model_tool_selector or _call_live_model
    selected_tool_call = selector(user_intent=user_intent, tools=tools)

    if selected_tool_call.name != "calendar_admin_create_event":
        return {
            "decision_kind": decision_kind,
            "prompt_to_user": prompt_to_user,
            "exposed_tool_names": exposed_tool_names,
            "hidden_tool_names": hidden_tool_names,
            "protected_tool_exposed": protected_tool_exposed,
            "model_selected_tool_name": selected_tool_call.name,
            "executed": False,
            "blocked_reason": (
                "model did not select protected admin tool"
                if protected_tool_exposed
                else "protected admin tool was not exposed to the model"
            ),
            "tool_result": None,
            "execution_log": host.execution_log.copy(),
            "side_effect_path": str(side_effect_store.artifact_path),
            "side_effect_count": side_effect_store.count(),
        }

    if not protected_tool_exposed:
        return {
            "decision_kind": decision_kind,
            "prompt_to_user": prompt_to_user,
            "exposed_tool_names": exposed_tool_names,
            "hidden_tool_names": hidden_tool_names,
            "protected_tool_exposed": False,
            "model_selected_tool_name": selected_tool_call.name,
            "executed": False,
            "blocked_reason": "calendar_admin state not authorized",
            "tool_result": None,
            "execution_log": host.execution_log.copy(),
            "side_effect_path": str(side_effect_store.artifact_path),
            "side_effect_count": side_effect_store.count(),
        }

    tool_call: McpToolCall = {
        "tool_name": "calendar_admin_create_event",
        "arguments": selected_tool_call.arguments,
    }
    tool_result = host.execute_mcp_tool(tool_call)
    side_effect_store.append(tool_call=tool_call)
    return {
        "decision_kind": decision_kind,
        "prompt_to_user": prompt_to_user,
        "exposed_tool_names": exposed_tool_names,
        "hidden_tool_names": hidden_tool_names,
        "protected_tool_exposed": True,
        "model_selected_tool_name": selected_tool_call.name,
        "executed": True,
        "blocked_reason": None,
        "tool_result": tool_result,
        "execution_log": host.execution_log.copy(),
        "side_effect_path": str(side_effect_store.artifact_path),
        "side_effect_count": side_effect_store.count(),
    }
