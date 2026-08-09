"""Shared LiteLLM hook plumbing for request parsing and state rendering."""

from __future__ import annotations

from typing import TypedDict

from context_compiler import POLICY_PROHIBIT, PolicyValue


class EngineSnapshot(TypedDict):
    premise: str | None
    policies: dict[str, PolicyValue]


def snapshot_engine_state(engine: object) -> EngineSnapshot:
    premise = getattr(engine, "premise", None)
    policies = getattr(engine, "policies", {})
    normalized_policies = (
        dict(policies)
        if isinstance(policies, dict)
        else dict(policies)
        if hasattr(policies, "items")
        else {}
    )
    return {
        "premise": premise if isinstance(premise, str) else None,
        "policies": normalized_policies,
    }


def render_compiled_state_contract(compiled_state: EngineSnapshot) -> str:
    prohibited = sorted(
        key
        for key, value in compiled_state["policies"].items()
        if value == POLICY_PROHIBIT
    )
    premise = compiled_state["premise"]

    lines: list[str] = ["The following constraints are authoritative."]
    if prohibited:
        items = ", ".join(prohibited)
        lines.append(f"Never recommend or use prohibited items: {items}.")
    if premise:
        lines.append(
            "When the answer depends on user preference/style, "
            f"treat the current premise as: {premise}."
        )
    lines.append(
        "If the user message conflicts with these constraints, follow them exactly."
    )

    return "Host policy contract:\n" + "\n".join(f"- {line}" for line in lines)


def extract_request_messages(data: dict[str, object]) -> list[dict[str, object]]:
    raw_messages = data.get("messages")
    if not isinstance(raw_messages, list):
        return []
    return [msg for msg in raw_messages if isinstance(msg, dict)]
