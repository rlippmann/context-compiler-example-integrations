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
    get_premise_value,
    is_clarify,
)
from context_compiler.engine import Engine

CONCISE_STYLE = "concise_style"
BOARD_UPDATE_CONTEXT = "draft is a board update summarizing quarterly results"
INCIDENT_HANDOFF_CONTEXT = (
    "draft is an internal engineering handoff for a sev-1 incident"
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a writing assistant. Help the user improve a draft while "
    "preserving the author's intent."
)
BOARD_UPDATE_CONTEXT_GUIDANCE = (
    "Document context: this draft is a board update summarizing quarterly "
    "results. Include the decision context, the most material business "
    "outcomes, major risks, and the clearest next-step summary."
)
INCIDENT_HANDOFF_CONTEXT_GUIDANCE = (
    "Document context: this draft is an internal engineering handoff for a "
    "sev-1 incident. Include the current incident status, confirmed technical "
    "facts, mitigations already attempted, open hypotheses, and immediate "
    "handoff risks."
)
CONCISE_GUIDANCE = "Use a concise writing style with short, direct sentences."


class PromptMessage(TypedDict):
    role: Literal["system", "user"]
    content: str


class PromptConstructionResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    model_call_ready: bool
    llm_call_performed: bool
    messages: list[PromptMessage]
    applied_premise: str | None
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

    return labels


def audience_guidance_from_premise(premise: str | None) -> str | None:
    """Map an authoritative document-context premise to host-owned guidance."""

    if premise == BOARD_UPDATE_CONTEXT:
        return BOARD_UPDATE_CONTEXT_GUIDANCE
    if premise == INCIDENT_HANDOFF_CONTEXT:
        return INCIDENT_HANDOFF_CONTEXT_GUIDANCE
    return None


def build_prompt_messages(
    *,
    state: State,
    user_text: str,
) -> tuple[list[PromptMessage], str | None, list[str]]:
    """Build host-owned prompt messages from authoritative compiler state."""

    premise = get_premise_value(state)
    audience_guidance = audience_guidance_from_premise(premise)
    style_labels = style_labels_from_state(state)
    system_lines = [DEFAULT_SYSTEM_PROMPT]

    if audience_guidance is not None:
        system_lines.append(audience_guidance)
    if CONCISE_STYLE in style_labels:
        system_lines.append(CONCISE_GUIDANCE)

    return (
        [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": user_text},
        ],
        premise,
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
            "applied_premise": None,
            "applied_style_labels": [],
            "blocked_reason": "clarification required before prompt construction",
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    messages, premise, style_labels = build_prompt_messages(
        state=authoritative_state,
        user_text=user_text,
    )
    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "model_call_ready": True,
        "llm_call_performed": False,
        "messages": messages,
        "applied_premise": premise,
        "applied_style_labels": style_labels,
        "blocked_reason": None,
    }


def run_demo() -> dict[str, PromptConstructionResult]:
    """Show how host-built prompts differ by authoritative state."""

    user_text = "Ignore the saved document context and write this like a casual post."

    default_engine = create_engine()
    premise_engine = create_engine()
    premise_engine.step(f"set premise {BOARD_UPDATE_CONTEXT}")
    policy_engine = create_engine()
    policy_engine.step(f"use {CONCISE_STYLE}")
    combined_engine = create_engine()
    combined_engine.step(f"set premise {BOARD_UPDATE_CONTEXT}")
    combined_engine.step(f"use {CONCISE_STYLE}")

    return {
        "default_prompt": prepare_prompt_turn(
            default_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
        "premise_prompt": prepare_prompt_turn(
            premise_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
        "policy_prompt": prepare_prompt_turn(
            policy_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
        "combined_prompt": prepare_prompt_turn(
            combined_engine,
            compiler_input=user_text,
            user_text=user_text,
        ),
    }


if __name__ == "__main__":
    print(run_demo())
