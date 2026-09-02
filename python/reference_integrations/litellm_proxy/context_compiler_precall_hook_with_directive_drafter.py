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
from functools import lru_cache
from typing import Any

try:
    from litellm.integrations.custom_logger import CustomLogger
except ModuleNotFoundError:
    # Keep this import path optional: CI/tests run without integration extras.
    # A tiny fallback base class keeps module imports deterministic so coverage
    # validates behavior instead of failing or silently skipping on missing litellm.
    class CustomLogger:  # type: ignore[no-redef]
        pass


from context_compiler import DecisionKind, Engine, NoDirectiveDecision
from context_compiler.grammar import CanonicalDirective
from context_compiler_directive_drafter import (
    DirectiveDrafter,
    DraftResult,
)
from context_compiler_directive_drafter.fallbacks.litellm import (
    create_litellm_fallback,
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
)

logger = logging.getLogger(__name__)

_SUPPORTED_CALL_TYPES = {
    "completion",
    "acompletion",
    "chat_completion",
    "achat_completion",
}

CHECKPOINT_STORE: CheckpointStore = InMemoryCheckpointStore()


@lru_cache(maxsize=8)
def _create_directive_drafter(
    model: str, api_key: str, api_base: str | None
) -> DirectiveDrafter:
    return DirectiveDrafter(
        fallback=create_litellm_fallback(
            model=model,
            api_key=api_key,
            api_base=api_base,
        ),
        fallback_source="litellm_fallback",
    )


def _get_directive_drafter() -> DirectiveDrafter:
    preprocessor_model = os.getenv("PREPROCESSOR_MODEL", "").strip()
    if not preprocessor_model:
        preprocessor_model = os.getenv("MODEL", "").strip()
    if not preprocessor_model:
        return DirectiveDrafter()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return DirectiveDrafter()
    return _create_directive_drafter(
        preprocessor_model, api_key, os.getenv("OPENAI_BASE_URL") or None
    )


def _draft_last_user_message(message: str) -> DraftResult:
    try:
        return _get_directive_drafter().draft_directive(message)
    except Exception:
        logger.debug("litellm_proxy: drafter_exception", exc_info=True)
        return DirectiveDrafter().draft_directive(message)


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

        engine = Engine()
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
        drafted_result: DraftResult | None = None
        decision: Any

        if latest_user_text is not None:
            drafted_result = _draft_last_user_message(latest_user_text)
            logger.debug("litellm_proxy: drafted_result=%r", drafted_result)
            if isinstance(drafted_result.result, CanonicalDirective):
                decision = engine.step(drafted_result.result.text)
            else:
                decision = NoDirectiveDecision()
        else:
            decision = NoDirectiveDecision()

        logger.debug("litellm_proxy: decision_kind=%s", decision.kind)

        if decision.kind == DecisionKind.ERROR:
            logger.debug("litellm_proxy: rejecting_failed_application=true")
            message = decision.message
            return (
                message if isinstance(message, str) and message else "Request rejected."
            )

        if session.mode == MODE_PERSISTENT and session.session_key is not None:
            CHECKPOINT_STORE.save(
                session.session_key,
                checkpoint_to_jsonable(engine.export_json()),
            )

        system_message: dict[str, object] = {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + render_compiled_state_contract(engine),
        }
        logger.debug("litellm_proxy: inject_system_message=true")
        # Preserve original request messages; drafting changes only compiler input.
        data["messages"] = [system_message, *request_messages]
        return data


proxy_handler_instance = ContextCompilerPreCallHookWithPreprocessor()
