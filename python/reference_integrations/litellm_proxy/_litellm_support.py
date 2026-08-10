"""Shared LiteLLM hook plumbing for request parsing and engine-state rendering."""

from __future__ import annotations

from context_compiler.engine import Engine

from context_compiler import POLICY_PROHIBIT


def render_compiled_state_contract(engine: Engine) -> str:
    prohibited = sorted(
        key for key, value in engine.policies.items() if value == POLICY_PROHIBIT
    )

    lines: list[str] = ["The following constraints are authoritative."]
    if prohibited:
        items = ", ".join(prohibited)
        lines.append(f"Never recommend or use prohibited items: {items}.")
    if engine.premise:
        lines.append(
            "When the answer depends on user preference/style, "
            f"treat the current premise as: {engine.premise}."
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
