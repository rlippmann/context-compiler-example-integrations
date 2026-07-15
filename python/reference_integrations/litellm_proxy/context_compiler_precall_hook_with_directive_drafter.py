"""LiteLLM Proxy pre-call hook with optional directive drafter on latest user message.

Architecture:
- Resolve explicit persistent or stateless mode for the current request.
- In persistent mode, restore compiler checkpoint by session key.
- Draft only the latest user message after restore.
- Call ``engine.step(...)`` exactly once for the current turn.
- Save checkpoint after each decision, including clarify.
- If clarification is required, block upstream model call.
- Otherwise inject compiled state guidance into a system message.
"""

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from typing import Any, cast

try:
    from litellm.integrations.custom_logger import CustomLogger
except ModuleNotFoundError:
    # Keep this import path optional: CI/tests run without integration extras.
    # A tiny fallback base class keeps module imports deterministic so coverage
    # validates behavior instead of failing or silently skipping on missing litellm.
    class CustomLogger:  # type: ignore[no-redef]
        pass


from context_compiler import (
    POLICY_PROHIBIT,
    State,
    create_engine,
    get_clarify_prompt,
    get_policy_items,
    get_premise_value,
    is_clarify,
)
from context_compiler.engine import DecisionKind
from context_compiler_directive_drafter import (
    PREPROCESS_OUTCOME_DIRECTIVE,
    parse_preprocessor_output,
    preprocess_heuristic,
    render_prompt,
)
from context_compiler_example_integrations.reference_integrations.litellm_proxy._checkpoint_support import (
    MODE_PERSISTENT,
    CheckpointStore,
    InMemoryCheckpointStore,
    checkpoint_from_jsonable,
    checkpoint_to_jsonable,
    extract_latest_user_text,
    resolve_session_context,
)

logger = logging.getLogger(__name__)

_SUPPORTED_CALL_TYPES = {
    "completion",
    "acompletion",
    "chat_completion",
    "achat_completion",
}

_PROMPTS_DIR = files("context_compiler_directive_drafter").joinpath("prompts")
CHECKPOINT_STORE: CheckpointStore = InMemoryCheckpointStore()


def _render_compiled_state_contract(compiled_state: State) -> str:
    prohibited = get_policy_items(compiled_state, POLICY_PROHIBIT)
    premise = get_premise_value(compiled_state)

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


def _extract_request_messages(data: dict[str, object]) -> list[dict[str, object]]:
    raw_messages = data.get("messages")
    if not isinstance(raw_messages, list):
        return []
    return [msg for msg in raw_messages if isinstance(msg, dict)]


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


def _prompt_file_path() -> Traversable:
    profile = os.getenv("PREPROCESSOR_PROMPT_PROFILE", "default").strip().lower()
    if profile == "llama":
        return _PROMPTS_DIR.joinpath("llama.txt")
    return _PROMPTS_DIR.joinpath("default.txt")


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


def _llm_fallback_preprocess(message: str, state: State) -> str | None:
    with as_file(_prompt_file_path()) as prompt_path:
        prompt = render_prompt(prompt_path, state)
    if prompt is None:
        return None

    preprocessor_model = os.getenv("PREPROCESSOR_MODEL", "").strip()
    if not preprocessor_model:
        preprocessor_model = os.getenv("MODEL", "").strip()
    if not preprocessor_model:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        completion = _get_litellm_completion()
    except ModuleNotFoundError:
        return None

    kwargs: dict[str, object] = {
        "model": preprocessor_model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
        ],
        "api_key": api_key,
        "temperature": 0,
    }
    api_base = os.getenv("OPENAI_BASE_URL")
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = completion(**kwargs)
        raw_output = _extract_response_content(response)
    except Exception:
        return None

    parsed = parse_preprocessor_output(raw_output)
    if parsed is None:
        return None
    return parsed


def _preprocess_last_user_message(message: str, state: State | None) -> str | None:
    try:
        heuristic_result = preprocess_heuristic(message)
        if (
            heuristic_result["outcome"] == PREPROCESS_OUTCOME_DIRECTIVE
            and heuristic_result["directive"]
        ):
            parsed = parse_preprocessor_output(heuristic_result["directive"])
            if parsed is not None:
                return parsed
    except Exception:
        logger.debug("litellm_proxy: heuristic_exception", exc_info=True)

    if state is None:
        return None

    try:
        return _llm_fallback_preprocess(message, state)
    except Exception:
        logger.debug("litellm_proxy: fallback_exception", exc_info=True)
        return None


class ContextCompilerPreCallHookWithPreprocessor(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,
        data: dict[str, object],
        call_type: str,
    ) -> dict[str, object] | str:
        del user_api_key_dict, cache
        logger.debug("litellm_proxy: call_type=%s", call_type)
        if call_type not in _SUPPORTED_CALL_TYPES:
            return data

        request_messages = _extract_request_messages(data)
        logger.debug("litellm_proxy: message_count=%d", len(request_messages))
        session = resolve_session_context(data)
        logger.debug(
            "litellm_proxy: mode=%s session_key_source=%s",
            session.mode,
            session.source,
        )
        if session.mode == MODE_PERSISTENT and session.session_key is None:
            return (
                "Context Compiler persistent mode requires a stable session key. "
                "Set context_compiler_session_key or "
                "metadata.context_compiler_session_key."
            )

        engine = create_engine()
        if session.mode == MODE_PERSISTENT and session.session_key is not None:
            checkpoint = CHECKPOINT_STORE.load(session.session_key)
            if checkpoint is not None:
                try:
                    engine.import_checkpoint_json(checkpoint_from_jsonable(checkpoint))
                except Exception as exc:
                    return (
                        "Context Compiler checkpoint load failed for session "
                        f"{session.session_key!r}: {exc}"
                    )

        latest_user_text = extract_latest_user_text(request_messages)
        logger.debug(
            "litellm_proxy: latest_user_text_present=%s", latest_user_text is not None
        )
        engine_input = latest_user_text
        drafted_input: str | None = None

        if latest_user_text is not None and not engine.has_pending_clarification():
            drafted_input = _preprocess_last_user_message(
                latest_user_text, engine.state
            )
            logger.debug("litellm_proxy: drafted_input=%r", drafted_input)
            if drafted_input is not None:
                engine_input = drafted_input

        if engine_input is not None:
            decision = engine.step(engine_input)
        else:
            decision = {
                "kind": DecisionKind.PASSTHROUGH,
                "state": engine.state,
                "prompt_to_user": None,
            }

        if session.mode == MODE_PERSISTENT and session.session_key is not None:
            CHECKPOINT_STORE.save(
                session.session_key,
                checkpoint_to_jsonable(engine.export_checkpoint_json()),
            )

        logger.debug("litellm_proxy: decision_kind=%s", decision["kind"])

        if is_clarify(decision):
            logger.debug("litellm_proxy: blocking_on_clarify=true")
            return get_clarify_prompt(decision) or "Confirmation required."

        compiled_state = engine.state
        system_message: dict[str, object] = {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + _render_compiled_state_contract(compiled_state),
        }
        logger.debug("litellm_proxy: inject_system_message=true")
        # Preserve original request messages; drafting changes only compiler input.
        data["messages"] = [system_message, *request_messages]
        return data


proxy_handler_instance = ContextCompilerPreCallHookWithPreprocessor()
