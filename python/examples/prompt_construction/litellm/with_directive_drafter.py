"""LiteLLM integration with optional directive drafter before Context Compiler.

Flow:
1. Extract user input
2. Run heuristic directive drafter
3. If no directive, run LLM fallback directive drafter using prompt files
4. Pass directive (or original input) to engine.step(...)
5. clarify -> return prompt_to_user (no model call)
6. update -> return deterministic acknowledgment text (no model call)
7. passthrough -> call LiteLLM with compiled state + user input

Intended host usage:
- collect user input
- call handle_turn(user_input, engine)
- display returned assistant text
"""

import logging
import os
import re
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from typing import TypedDict, cast

from context_compiler import (
    DecisionKind,
    DECISION_UPDATE,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    is_update,
)
from context_compiler.engine import Engine
from context_compiler_directive_drafter import (
    PREPROCESS_OUTCOME_DIRECTIVE,
    parse_preprocessor_output,
    preprocess_heuristic,
    render_prompt,
)

try:
    from .confirmation_helper import (
        is_confirmation_text,
        summarize_confirmation_update_from_checkpoint,
    )
except ImportError:
    from confirmation_helper import (
        is_confirmation_text,
        summarize_confirmation_update_from_checkpoint,
    )

from context_compiler_example_integrations.examples._shared.provider_mode import (
    print_startup_config,
    resolve_provider_config,
)

logger = logging.getLogger(__name__)

_PROMPTS_DIR = files("context_compiler_directive_drafter").joinpath("prompts")
# Example-only in-memory checkpoint store.
# This keeps continuation state only for the current process lifetime.
# Real deployments should persist checkpoints externally (DB/Redis/etc.),
# or restart continuity for pending flows will be lost.
_CHECKPOINTS_BY_SESSION_KEY: dict[str, str] = {}
_RESTORED_ENGINE_BY_SESSION_KEY: dict[str, int] = {}
SHOW_CONTEXT_COMPILER_TRACE = False


class _EngineSnapshot(TypedDict):
    premise: str | None
    policies: dict[str, PolicyValue]


def _is_directive_shaped_input(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.strip()).lower()
    return (
        normalized.startswith("use")
        or normalized.startswith("prohibit")
        or normalized.startswith("remove policy")
        or normalized.startswith("set premise")
        or normalized.startswith("change premise")
        or normalized.startswith("clear")
        or normalized.startswith("reset")
    )


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
    preprocessor_output: str | None,
    decision: object,
    state_before: object,
    state_after: object,
    llm_called: bool,
) -> str:
    kind = decision.get("kind", "unknown") if isinstance(decision, dict) else "unknown"
    lines = [
        "Context Compiler trace",
        f"- original_input: {original_input}",
        f"- compiler_input: {compiler_input}",
        f"- preprocessor_output: {preprocessor_output if preprocessor_output is not None else '(none)'}",
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


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


def _render_compiled_state_contract(compiled_state: _EngineSnapshot) -> str:
    premise = compiled_state["premise"]
    use_items = sorted(
        key for key, value in compiled_state["policies"].items() if value == POLICY_USE
    )
    prohibit_items = sorted(
        key
        for key, value in compiled_state["policies"].items()
        if value == POLICY_PROHIBIT
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


def _build_messages(
    user_input: str, compiled_state: _EngineSnapshot
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + _render_compiled_state_contract(compiled_state),
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


def _prompt_file_path() -> Traversable:
    profile = os.getenv("PREPROCESSOR_PROMPT_PROFILE", "default").strip().lower()
    if profile == "llama":
        return _PROMPTS_DIR.joinpath("llama.txt")
    return _PROMPTS_DIR.joinpath("default.txt")


def _llm_fallback_preprocess(message: str, state: _EngineSnapshot) -> str | None:
    with as_file(_prompt_file_path()) as prompt_path:
        prompt = render_prompt(prompt_path, state)
    if prompt is None:
        return None

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
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "api_base": config.base_url,
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key

    try:
        response = completion(**kwargs)
        raw_output = _extract_response_content(response)
    except Exception:
        return None

    parsed = parse_preprocessor_output(raw_output)
    if parsed is None:
        return None
    return parsed


def _preprocess_user_input(message: str, state: _EngineSnapshot) -> str | None:
    # Heuristic first (fast + high precision), then optional LLM fallback.
    try:
        heuristic_result = preprocess_heuristic(message)
        logger.debug("preprocessor: heuristic_outcome=%s", heuristic_result["outcome"])
        if (
            heuristic_result["outcome"] == PREPROCESS_OUTCOME_DIRECTIVE
            and heuristic_result["directive"]
        ):
            parsed = parse_preprocessor_output(heuristic_result["directive"])
            logger.debug(
                "preprocessor: heuristic_directive=%r", heuristic_result["directive"]
            )
            if parsed is not None:
                return parsed
    except Exception:
        logger.debug("preprocessor: heuristic_exception", exc_info=True)

    if _is_directive_shaped_input(message):
        return None

    try:
        fallback_directive = _llm_fallback_preprocess(message, state)
        logger.debug("preprocessor: fallback_directive=%r", fallback_directive)
        return fallback_directive
    except Exception:
        # Safe no-op fallback: if preprocessor path fails, preserve basic behavior.
        return None


def _restore_session_checkpoint_if_needed(
    engine: Engine, session_key: str | None
) -> None:
    if session_key is None:
        return
    engine_id = id(engine)
    if _RESTORED_ENGINE_BY_SESSION_KEY.get(session_key) == engine_id:
        return

    checkpoint = _CHECKPOINTS_BY_SESSION_KEY.get(session_key)
    if checkpoint is not None:
        engine.import_checkpoint_json(checkpoint)
    _RESTORED_ENGINE_BY_SESSION_KEY[session_key] = engine_id


def _persist_session_checkpoint_if_needed(
    engine: Engine, kind: str, session_key: str | None
) -> None:
    if session_key is None:
        return
    if kind not in {DECISION_UPDATE, DecisionKind.ERROR.value}:
        return
    _CHECKPOINTS_BY_SESSION_KEY[session_key] = engine.export_checkpoint_json()


def _render_item_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _near_miss_directive_clarify(value: str) -> str | None:
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


def _summarize_confirmation_update(user_input: str, checkpoint: object) -> str:
    summarize_fn: Callable[[str, object], str] = (
        summarize_confirmation_update_from_checkpoint
    )
    return summarize_fn(user_input, checkpoint)


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
    preprocessor_output: str | None,
    decision: object,
    state_before: object,
    state_after: object,
    llm_called: bool,
) -> str:
    if not SHOW_CONTEXT_COMPILER_TRACE:
        return response_text
    trace_text = _build_trace_text(
        original_input=original_input,
        compiler_input=compiler_input,
        preprocessor_output=preprocessor_output,
        decision=decision,
        state_before=state_before,
        state_after=state_after,
        llm_called=llm_called,
    )
    return f"{response_text}\n\n{trace_text}"


def handle_turn(
    user_input: str, engine: Engine, *, session_key: str | None = None
) -> str:
    _restore_session_checkpoint_if_needed(engine, session_key)
    state_before = _snapshot_engine_state(engine)
    has_pending_before = engine.has_pending_clarification()
    checkpoint_before = engine.export_checkpoint() if has_pending_before else None
    preprocessd: str | None = None
    if engine.has_pending_clarification():
        compile_input = user_input
    else:
        preprocessd = _preprocess_user_input(user_input, _snapshot_engine_state(engine))
        compile_input = preprocessd if preprocessd else user_input
    logger.debug(
        "preprocessor: engine_input=%s",
        "directive" if preprocessd else f"user_input len={len(user_input)}",
    )

    decision = engine.step(compile_input)
    if decision["kind"] == DecisionKind.ERROR:
        kind = DecisionKind.ERROR.value
    elif is_update(decision):
        kind = DECISION_UPDATE
    else:
        kind = DecisionKind.NO_DIRECTIVE.value
    logger.debug("preprocessor: decision=%s", kind)
    near_miss_prompt = _near_miss_directive_clarify(user_input)

    if decision["kind"] == DecisionKind.ERROR:
        _persist_session_checkpoint_if_needed(engine, kind, session_key)
        response_text = near_miss_prompt or decision["message"] or ""
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=decision,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    if near_miss_prompt is not None and decision["kind"] == DecisionKind.NO_DIRECTIVE:
        return _append_trace(
            near_miss_prompt,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision={"kind": DecisionKind.ERROR, "message": near_miss_prompt},
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    _persist_session_checkpoint_if_needed(engine, kind, session_key)
    if (
        is_update(decision)
        and is_confirmation_text(user_input)
        and checkpoint_before is not None
    ):
        response_text = _summarize_confirmation_update(user_input, checkpoint_before)
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=decision,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    if is_update(decision):
        response_text = _summarize_update_from_input(compile_input)
        return _append_trace(
            response_text,
            original_input=user_input,
            compiler_input=compile_input,
            preprocessor_output=preprocessd,
            decision=decision,
            state_before=state_before,
            state_after=_snapshot_engine_state(engine),
            llm_called=False,
        )
    messages = _build_messages(user_input, _snapshot_engine_state(engine))
    response_text = _call_litellm(messages)
    return _append_trace(
        response_text,
        original_input=user_input,
        compiler_input=compile_input,
        preprocessor_output=preprocessd,
        decision=decision,
        state_before=state_before,
        state_after=_snapshot_engine_state(engine),
        llm_called=True,
    )
