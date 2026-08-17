"""LiteLLM integration with optional directive drafter before Context Compiler.

Flow:
1. Extract user input
2. Ask DirectiveDrafter to draft one directive, using LiteLLM only as fallback
3. Observe the returned DraftResult and extract drafted directive text when present
4. Pass drafted directive text, or the original input, to engine.step(...)
5. If the compiler returns an error or near-miss rejection, return that text locally
6. If the compiler applies an update, return a deterministic acknowledgment locally
7. Otherwise call LiteLLM with compiled state + user input

Intended host usage:
- collect user input
- call handle_turn(user_input, engine)
- display returned assistant text
"""

import logging
import os
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
from context_compiler.grammar import CanonicalDirective
from context_compiler_directive_drafter import (
    DraftResult,
    DirectiveDrafter,
    NoDirective,
    UnknownDirective,
    get_converter_prompt,
)

from context_compiler_example_integrations.examples._shared.provider_mode import (
    print_startup_config,
    resolve_provider_config,
)

logger = logging.getLogger(__name__)
SHOW_CONTEXT_COMPILER_TRACE = False


class _LiteLLMCallKwargs(TypedDict, total=False):
    model: str
    messages: list[dict[str, str]]
    api_key: str
    temperature: float
    api_base: str


ApprovalHandler = Callable[[str], bool]


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


_DIRECTIVE_DRAFTER = DirectiveDrafter(
    fallback=lambda message: _llm_fallback_candidate(message),
    fallback_source="litellm_fallback",
)


def _render_state_lines(
    premise: str | None, policies: Mapping[str, PolicyValue]
) -> list[str]:
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
    preprocessor_output: str | None,
    decision: Decision | DecisionKind,
    premise_before: str | None,
    policies_before: Mapping[str, PolicyValue],
    premise_after: str | None,
    policies_after: Mapping[str, PolicyValue],
    llm_called: bool,
) -> str:
    kind = decision if isinstance(decision, DecisionKind) else decision.kind
    lines = [
        "Context Compiler trace",
        f"- original_input: {original_input}",
        f"- compiler_input: {compiler_input}",
        f"- preprocessor_output: {preprocessor_output if preprocessor_output is not None else '(none)'}",
        f"- decision: {kind}",
        f"- llm_called: {'yes' if llm_called else 'no'}",
    ]
    lines.append(
        "- state_changed: "
        + (
            "yes"
            if premise_before != premise_after
            or dict(policies_before) != dict(policies_after)
            else "no"
        )
    )
    lines.append("state_before:")
    lines.extend(_render_state_lines(premise_before, policies_before))
    lines.append("state_after:")
    lines.extend(_render_state_lines(premise_after, policies_after))
    return "\n".join(lines)


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


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
        completion = _get_litellm_completion()
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "litellm is required. Install with: pip install litellm"
        ) from exc

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

    response = completion(**kwargs)
    content = _extract_response_content(response)
    if content is None:
        raise RuntimeError("LiteLLM response missing choices[0].message.content")
    return content


def _llm_fallback_candidate(message: str) -> str | None:
    try:
        completion = _get_litellm_completion()
    except ModuleNotFoundError:
        return None

    try:
        config = resolve_provider_config(default_model="openai/gpt-4o-mini")
    except RuntimeError:
        return None
    if config.mode == "openai" and not config.api_key:
        return None
    preprocessor_model = os.getenv("PREPROCESSOR_MODEL", "").strip()
    if not preprocessor_model:
        preprocessor_model = os.getenv("MODEL", "openai/gpt-4o-mini")

    kwargs: _LiteLLMCallKwargs = {
        "model": preprocessor_model,
        "messages": [
            {"role": "system", "content": get_converter_prompt()},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "api_base": config.base_url,
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key

    try:
        response = completion(**kwargs)
        return _extract_response_content(response)
    except Exception:
        return None


def _preprocess_user_input(message: str) -> str | None:
    try:
        drafted_result = _DIRECTIVE_DRAFTER.draft_directive(message)
        logger.debug("preprocessor: drafted_result=%r", drafted_result)
        return _extract_drafted_text(drafted_result)
    except Exception:
        # Safe no-op fallback: if drafter path fails, preserve basic behavior.
        logger.debug("preprocessor: drafter_exception", exc_info=True)
        return None
    return None


def _extract_drafted_text(drafted_result: DraftResult) -> str | None:
    result = drafted_result.result
    if isinstance(result, CanonicalDirective):
        return result.text
    if isinstance(result, NoDirective):
        return None
    if isinstance(result, UnknownDirective):
        return None
    return None


def _append_trace(
    response_text: str,
    *,
    original_input: str,
    compiler_input: str,
    preprocessor_output: str | None,
    decision: Decision | DecisionKind,
    state_before: tuple[str | None, dict[str, PolicyValue]],
    state_after: tuple[str | None, dict[str, PolicyValue]],
    llm_called: bool,
) -> str:
    if not SHOW_CONTEXT_COMPILER_TRACE:
        return response_text
    trace_text = _build_trace_text(
        original_input=original_input,
        compiler_input=compiler_input,
        preprocessor_output=preprocessor_output,
        decision=decision,
        premise_before=state_before[0],
        policies_before=state_before[1],
        premise_after=state_after[0],
        policies_after=state_after[1],
        llm_called=llm_called,
    )
    return f"{response_text}\n\n{trace_text}"


def _default_approval_handler(directive_text: str) -> bool:
    print("This is what I think the directive is:")
    print(directive_text)
    response = input("Apply it? (y/n)\n")
    return response.strip().lower() == "y"


def handle_turn(
    user_input: str,
    engine: Engine,
    approval_handler: ApprovalHandler = _default_approval_handler,
) -> str:
    state_before = (engine.premise, dict(engine.policies))
    preprocessd = _preprocess_user_input(user_input)
    if preprocessd is None:
        messages = _build_messages(user_input, engine)
        response_text = _call_litellm(messages)
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=user_input,
            preprocessor_output=None,
            decision=DecisionKind.NO_DIRECTIVE,
            state_before=state_before,
            state_after=(engine.premise, dict(engine.policies)),
            llm_called=True,
        )

    compile_input = preprocessd
    logger.debug("preprocessor: engine_input=directive")
    approved = approval_handler(compile_input)
    if not approved:
        return _append_trace(
            "Directive rejected. No state change applied.",
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=DecisionKind.NO_DIRECTIVE,
            state_before=state_before,
            state_after=(engine.premise, dict(engine.policies)),
            llm_called=False,
        )

    decision = engine.step(compile_input)
    if decision.kind == DecisionKind.ERROR:
        kind = DecisionKind.ERROR.value
    elif decision.kind == DecisionKind.UPDATE:
        kind = DECISION_UPDATE
    else:
        kind = DecisionKind.NO_DIRECTIVE.value
    logger.debug("preprocessor: decision=%s", kind)

    if decision.kind == DecisionKind.ERROR:
        response_text = (
            decision.message if decision.kind == DecisionKind.ERROR else None or ""
        )
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=decision,
            state_before=state_before,
            state_after=(engine.premise, dict(engine.policies)),
            llm_called=False,
        )
    if decision.kind == DecisionKind.UPDATE:
        response_text = "State updated."
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=decision,
            state_before=state_before,
            state_after=(engine.premise, dict(engine.policies)),
            llm_called=False,
        )
    messages = _build_messages(user_input, engine)
    response_text = _call_litellm(messages)
    return _append_trace(
        response_text,
        original_input=user_input,
        compiler_input=compile_input,
        preprocessor_output=preprocessd,
        decision=decision,
        state_before=state_before,
        state_after=(engine.premise, dict(engine.policies)),
        llm_called=True,
    )
