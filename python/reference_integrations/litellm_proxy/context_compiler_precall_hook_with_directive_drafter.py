"""LiteLLM Proxy pre-call hook with optional directive drafter on latest user message.

Architecture:
- Resolve explicit persistent or stateless mode for the current request.
- In persistent mode, restore compiler checkpoint by session key.
- Draft only the latest user message after restore.
- Call ``engine.step(...)`` exactly once for the current turn.
- Save checkpoints only after successful authoritative state transitions.
- If directive application fails, reject the current request without persisting
  failed-turn engine state.
- Otherwise inject compiled state guidance into a system message.
"""

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
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
    DecisionKind,
    create_engine,
)
from context_compiler.grammar import CanonicalDirective
from context_compiler_directive_drafter import (
    DRAFT_OUTCOME_DIRECTIVE,
    DRAFT_OUTCOME_NO_DIRECTIVE,
    DirectiveDrafter,
    DraftResult,
    NoDirective,
    UnknownDirective,
    parse_preprocessor_output,
    validate_preprocessor_output,
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
from context_compiler_example_integrations.reference_integrations.litellm_proxy._litellm_support import (
    extract_request_messages,
    render_compiled_state_contract,
    snapshot_engine_state,
)

logger = logging.getLogger(__name__)

_SUPPORTED_CALL_TYPES = {
    "completion",
    "acompletion",
    "chat_completion",
    "achat_completion",
}

CHECKPOINT_STORE: CheckpointStore = InMemoryCheckpointStore()
_FALLBACK_SYSTEM_PROMPT = (
    "Convert the latest user message into exactly one valid Context Compiler "
    "directive, or output <NO_DIRECTIVE>. Use only these directive forms: "
    "set premise <value>, change premise to <value>, use <item>, prohibit "
    "<item>, remove policy <item>, use <new item> instead of <old item>, "
    "clear premise, reset policies, clear state. If the message is ambiguous, "
    "not a direct instruction to change compiler state, or could imply more "
    "than one instruction, output <NO_DIRECTIVE>. Do not explain."
)


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


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


def _llm_fallback_draft(message: str) -> DraftResult:
    preprocessor_model = os.getenv("PREPROCESSOR_MODEL", "").strip()
    if not preprocessor_model:
        preprocessor_model = os.getenv("MODEL", "").strip()
    if not preprocessor_model:
        return DraftResult(
            source="litellm_fallback",
            result=UnknownDirective(reason="fallback_model_unconfigured"),
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return DraftResult(
            source="litellm_fallback",
            result=UnknownDirective(reason="fallback_api_key_missing"),
        )

    try:
        completion = _get_litellm_completion()
    except ModuleNotFoundError:
        return DraftResult(
            source="litellm_fallback",
            result=UnknownDirective(reason="fallback_litellm_unavailable"),
        )

    kwargs: dict[str, object] = {
        "model": preprocessor_model,
        "messages": [
            {"role": "system", "content": _FALLBACK_SYSTEM_PROMPT},
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
        return DraftResult(
            source="litellm_fallback",
            result=UnknownDirective(reason="fallback_completion_failed"),
        )

    validated = validate_preprocessor_output(raw_output)
    if validated["classification"] == DRAFT_OUTCOME_DIRECTIVE:
        parsed = parse_preprocessor_output(raw_output)
        if parsed is not None:
            return DraftResult(source="litellm_fallback", result=parsed)
        return DraftResult(
            source="litellm_fallback",
            result=UnknownDirective(reason="invalid_canonical_directive"),
        )
    if validated["classification"] == DRAFT_OUTCOME_NO_DIRECTIVE:
        return DraftResult(
            source="litellm_fallback",
            result=NoDirective(reason="fallback_confident_non_directive"),
        )
    return DraftResult(
        source="litellm_fallback",
        result=UnknownDirective(reason="fallback_unresolved"),
    )


def _draft_last_user_message(message: str) -> DraftResult:
    drafter = DirectiveDrafter(fallback=_llm_fallback_draft)
    return drafter.draft_directive(message)


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

        request_messages = extract_request_messages(data)
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
                    engine.import_json(checkpoint_from_jsonable(checkpoint))
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
        drafted_result: DraftResult | None = None

        if latest_user_text is not None:
            drafted_result = _draft_last_user_message(latest_user_text)
            logger.debug("litellm_proxy: drafted_result=%r", drafted_result)
            if isinstance(drafted_result.result, CanonicalDirective):
                engine_input = drafted_result.result.text

        if engine_input is not None:
            decision = engine.step(engine_input)
        else:
            decision = {"kind": DecisionKind.NO_DIRECTIVE, "message": None}

        logger.debug("litellm_proxy: decision_kind=%s", decision["kind"])

        if decision["kind"] == DecisionKind.ERROR:
            logger.debug("litellm_proxy: rejecting_failed_application=true")
            return decision.get("message") or "Request rejected."

        if session.mode == MODE_PERSISTENT and session.session_key is not None:
            CHECKPOINT_STORE.save(
                session.session_key,
                checkpoint_to_jsonable(engine.export_json()),
            )

        compiled_state = snapshot_engine_state(engine)
        system_message: dict[str, object] = {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + render_compiled_state_contract(compiled_state),
        }
        logger.debug("litellm_proxy: inject_system_message=true")
        # Preserve original request messages; drafting changes only compiler input.
        data["messages"] = [system_message, *request_messages]
        return data


proxy_handler_instance = ContextCompilerPreCallHookWithPreprocessor()
