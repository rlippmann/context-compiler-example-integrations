"""Minimal LiteLLM integration with Context Compiler.

Flow:
1. Call engine.step(user_input)
2. error -> return prompt_to_user (no model call)
3. update -> return deterministic acknowledgment text (no model call)
4. passthrough -> call LiteLLM with compiled state + user input

Intended host usage:
- collect user input
- call handle_turn(user_input, engine)
- display returned assistant text
"""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import TypedDict, cast

from context_compiler import (
    Decision,
    DecisionKind,
    DECISION_UPDATE,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    Engine,
)

from context_compiler_example_integrations.examples._shared.provider_mode import (
    print_startup_config,
    resolve_provider_config,
)

logger = logging.getLogger(__name__)
SHOW_CONTEXT_COMPILER_TRACE = False


class _EngineSnapshot(TypedDict):
    premise: str | None
    policies: dict[str, PolicyValue]


class _LiteLLMCallKwargs(TypedDict, total=False):
    model: str
    messages: list[dict[str, str]]
    api_key: str
    temperature: float
    api_base: str


def _extract_response_content(response: object) -> str | None:
    if isinstance(response, Mapping):
        choices = response.get("choices")
        if isinstance(choices, Sequence) and choices:
            first = choices[0]
            if isinstance(first, Mapping):
                message = first.get("message")
                if isinstance(message, Mapping):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

    choices_attr = getattr(response, "choices", None)
    if isinstance(choices_attr, Sequence) and choices_attr:
        first = choices_attr[0]
        message_attr = getattr(first, "message", None)
        content_attr = getattr(message_attr, "content", None)
        if isinstance(content_attr, str):
            return content_attr

    return None


def _snapshot_engine_state(engine: Engine) -> _EngineSnapshot:
    return {"premise": engine.premise, "policies": dict(engine.policies)}


def _render_state_lines(state: object) -> list[str]:
    if not isinstance(state, dict):
        return ["- unavailable"]
    raw_policies = state.get("policies")
    policies = raw_policies if isinstance(raw_policies, dict) else {}
    premise = state.get("premise")
    use_items = sorted(
        key
        for key, value in policies.items()
        if value == POLICY_USE and isinstance(key, str)
    )
    prohibit_items = sorted(
        key
        for key, value in policies.items()
        if value == POLICY_PROHIBIT and isinstance(key, str)
    )

    lines = [f"- premise: {premise if premise is not None else '(none)'}"]
    lines.append(f"- use: {', '.join(use_items) if use_items else '(none)'}")
    lines.append(
        f"- prohibit: {', '.join(prohibit_items) if prohibit_items else '(none)'}"
    )
    return lines


def _build_trace_text(
    *,
    original_input: str,
    compiler_input: str,
    decision: Decision | DecisionKind,
    state_before: object,
    state_after: object,
    llm_called: bool,
) -> str:
    kind = decision if isinstance(decision, DecisionKind) else decision.kind
    lines = [
        "Context Compiler trace",
        f"- original_input: {original_input}",
        f"- compiler_input: {compiler_input}",
        f"- decision: {kind}",
        f"- llm_called: {'yes' if llm_called else 'no'}",
    ]
    if isinstance(state_before, dict) and isinstance(state_after, dict):
        lines.append(
            f"- state_changed: {'yes' if state_before != state_after else 'no'}"
        )
    lines.append("state_before:")
    lines.extend(_render_state_lines(state_before))
    lines.append("state_after:")
    lines.extend(_render_state_lines(state_after))
    return "\n".join(lines)


def _render_compiled_state_contract(engine: Engine) -> str:
    premise = engine.premise
    use_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_USE
    )
    prohibit_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_PROHIBIT
    )

    lines: list[str] = ["The following constraints are authoritative."]
    if premise:
        lines.append(f"Current premise: {premise}.")
    if use_items:
        lines.append("Items marked use: " + ", ".join(use_items) + ".")
    if prohibit_items:
        lines.append("Items marked prohibit: " + ", ".join(prohibit_items) + ".")
    lines.append("If user text conflicts with constraints, follow constraints exactly.")

    return "Host policy contract:\n" + "\n".join(f"- {line}" for line in lines)


def _build_messages(user_input: str, engine: Engine) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + _render_compiled_state_contract(engine),
        },
        {"role": "user", "content": user_input},
    ]


def _call_litellm(messages: list[dict[str, str]]) -> str:
    try:
        litellm_module = import_module("litellm")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "litellm is required. Install with: pip install litellm"
        ) from exc
    completion_fn = cast(Callable[..., object], litellm_module.completion)

    config = resolve_provider_config(default_model="openai/gpt-4o-mini")
    print_startup_config(config, logger=logger)

    kwargs: _LiteLLMCallKwargs = {
        "model": config.model,
        "messages": messages,
        "temperature": 0,
        "api_base": config.base_url,
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key

    response = completion_fn(**kwargs)
    content = _extract_response_content(response)
    if content is None:
        raise RuntimeError("LiteLLM response missing choices[0].message.content")
    return content


def _render_item_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _near_miss_directive_error(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value.strip())
    lower = normalized.lower()

    if lower in {"reset premise", "reset premises", "clear premises"}:
        return "Unknown directive.\nUse 'clear premise' or 'reset policies'."
    if lower.startswith("set premise to "):
        return "Invalid premise syntax.\nUse 'set premise <value>'."
    if lower.startswith("change premise ") and not lower.startswith(
        "change premise to "
    ):
        return "Invalid premise syntax.\nUse 'change premise to <value>'."
    return None


def _summarize_update_from_input(user_input: str) -> str:
    normalized = re.sub(r"\s+", " ", user_input.strip())
    lower = normalized.lower()

    if lower == "clear state":
        return "State cleared."
    if lower == "clear premise":
        return "Premise cleared."
    if lower == "reset policies":
        return "Policies reset."

    replacement_match = re.match(
        r"^use\s+(.+?)\s+instead\s+of\s+(.+)$", normalized, flags=re.IGNORECASE
    )
    if replacement_match is not None:
        item = _render_item_label(replacement_match.group(1).rstrip(" .!?"))
        if item:
            return f"State updated: Use {item}."

    use_match = re.match(r"^use\s+(.+)$", normalized, flags=re.IGNORECASE)
    if use_match is not None:
        item = _render_item_label(use_match.group(1).rstrip(" .!?"))
        if item:
            return f"State updated: Use {item}."

    prohibit_match = re.match(r"^prohibit\s+(.+)$", normalized, flags=re.IGNORECASE)
    if prohibit_match is not None:
        item = _render_item_label(prohibit_match.group(1).rstrip(" .!?"))
        if item:
            return f"State updated: Prohibit {item}."

    remove_policy_match = re.match(
        r"^remove\s+policy\s+(.+)$", normalized, flags=re.IGNORECASE
    )
    if remove_policy_match is not None:
        item = _render_item_label(remove_policy_match.group(1).rstrip(" .!?"))
        if item:
            return f"State updated: Removed policy {item}."

    return "State updated."


def _append_trace(
    response_text: str,
    *,
    original_input: str,
    compiler_input: str,
    decision: Decision | DecisionKind,
    state_before: object,
    state_after: object,
    llm_called: bool,
) -> str:
    if not SHOW_CONTEXT_COMPILER_TRACE:
        return response_text
    trace_text = _build_trace_text(
        original_input=original_input,
        compiler_input=compiler_input,
        decision=decision,
        state_before=state_before,
        state_after=state_after,
        llm_called=llm_called,
    )
    return f"{response_text}\n\n{trace_text}"


def handle_turn(user_input: str, engine: Engine) -> str:
    state_before = _snapshot_engine_state(engine)
    logger.debug("litellm_basic: engine_input=%s", f"user_input len={len(user_input)}")
    decision = engine.step(user_input)
    if decision.kind == DecisionKind.ERROR:
        kind = DecisionKind.ERROR.value
    elif decision.kind == DecisionKind.UPDATE:
        kind = DECISION_UPDATE
    else:
        kind = DecisionKind.NO_DIRECTIVE.value
    logger.debug("litellm_basic: decision=%s", kind)
    near_miss_prompt = _near_miss_directive_error(user_input)

    if decision.kind == DecisionKind.ERROR:
        response_text = (
            near_miss_prompt or decision.message
            if decision.kind == DecisionKind.ERROR
            else None or ""
        )
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=user_input,
            decision=decision,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    if near_miss_prompt is not None and decision.kind == DecisionKind.NO_DIRECTIVE:
        return _append_trace(
            near_miss_prompt,
            original_input=user_input,
            compiler_input=user_input,
            decision=DecisionKind.ERROR,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    if decision.kind == DecisionKind.UPDATE:
        response_text = _summarize_update_from_input(user_input)
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=user_input,
            decision=decision,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )

    messages = _build_messages(user_input, engine)
    response_text = _call_litellm(messages)
    return _append_trace(
        response_text,
        original_input=user_input,
        compiler_input=user_input,
        decision=decision,
        state_before=state_before,
        state_after=_snapshot_engine_state(engine),
        llm_called=True,
    )
