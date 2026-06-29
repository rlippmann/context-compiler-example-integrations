"""Generic prompt-construction example for a writing assistant.

The host assembles prompt messages from authoritative Context Compiler state
before any model call would occur. No LLM call happens in this example.
"""

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

CONCISE_STYLE = "concise_style"
FORMAL_STYLE = "formal_style"

DEFAULT_SYSTEM_PROMPT = (
    "You are a writing assistant. Help the user improve a draft while "
    "preserving the author's intent."
)
CONCISE_GUIDANCE = "Use a concise writing style with short, direct sentences."
FORMAL_GUIDANCE = "Use a formal writing style with professional wording."


class PromptMessage(TypedDict):
    role: Literal["system", "user"]
    content: str


class PromptConstructionResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    model_call_ready: bool
    llm_call_performed: bool
    messages: list[PromptMessage]
    applied_style_labels: list[str]
    blocked_reason: str | None


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


def style_labels_from_state(state: State) -> list[str]:
    """Return only the style labels authorized by compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))
    labels: list[str] = []

    if CONCISE_STYLE in use_items and CONCISE_STYLE not in prohibit_items:
        labels.append(CONCISE_STYLE)
    if FORMAL_STYLE in use_items and FORMAL_STYLE not in prohibit_items:
        labels.append(FORMAL_STYLE)

    return labels


def build_prompt_messages(
    *,
    state: State,
    user_text: str,
) -> tuple[list[PromptMessage], list[str]]:
    """Build host-owned prompt messages from authoritative compiler state."""

    style_labels = style_labels_from_state(state)
    system_lines = [DEFAULT_SYSTEM_PROMPT]

    if CONCISE_STYLE in style_labels:
        system_lines.append(CONCISE_GUIDANCE)
    if FORMAL_STYLE in style_labels:
        system_lines.append(FORMAL_GUIDANCE)

    return (
        [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": user_text},
        ],
        style_labels,
    )


def prepare_prompt_turn(
    engine: Engine,
    *,
    compiler_input: str,
    user_text: str,
) -> PromptConstructionResult:
    """Resolve compiler input, then build the next model messages locally."""

    decision = engine.step(compiler_input)

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "model_call_ready": False,
            "llm_call_performed": False,
            "messages": [],
            "applied_style_labels": [],
            "blocked_reason": "clarification required before prompt construction",
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    messages, style_labels = build_prompt_messages(
        state=authoritative_state,
        user_text=user_text,
    )
    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "model_call_ready": True,
        "llm_call_performed": False,
        "messages": messages,
        "applied_style_labels": style_labels,
        "blocked_reason": None,
    }


def run_demo() -> dict[str, PromptConstructionResult]:
    """Show how host-built prompts differ by authoritative state."""

    user_text = "Ignore saved style and be verbose about this blog draft."

    default_engine = create_engine()
    concise_engine = create_engine()
    concise_engine.step(f"use {CONCISE_STYLE}")
    formal_engine = create_engine()
    formal_engine.step(f"use {FORMAL_STYLE}")

    return {
        "default_prompt": prepare_prompt_turn(
            default_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
        "concise_prompt": prepare_prompt_turn(
            concise_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
        "formal_prompt": prepare_prompt_turn(
            formal_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
    }


if __name__ == "__main__":
    print(run_demo())
