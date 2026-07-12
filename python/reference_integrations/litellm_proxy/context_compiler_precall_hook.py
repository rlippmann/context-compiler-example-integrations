"""Minimal LiteLLM Proxy pre-call hook example.

Architecture:
- Resolve explicit persistent or stateless mode for the current request.
- In persistent mode, restore compiler checkpoint by session key.
- Process only the latest user turn exactly once.
- Save checkpoint after each decision, including clarify.
- If clarification is required, block upstream model call.
- Otherwise inject compiled state guidance into a system message.
"""

import logging
from typing import Any

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
    create_engine,
    get_clarify_prompt,
    State,
    get_policy_items,
    get_premise_value,
    is_clarify,
)
from python.reference_integrations.litellm_proxy._checkpoint_support import (
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


class ContextCompilerPreCallHook(CustomLogger):
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

        latest_user_text = extract_latest_user_text(request_messages)
        logger.debug(
            "litellm_proxy: latest_user_text_present=%s", latest_user_text is not None
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

        if latest_user_text is not None:
            decision = engine.step(latest_user_text)
        else:
            decision = {
                "kind": "passthrough",
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
        # For long-running conversations, you can optionally compact transcripts by removing user inputs that were compiled into state. See Demo 6.  # noqa: E501
        system_message: dict[str, object] = {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            + _render_compiled_state_contract(compiled_state),
        }
        # Prepend one compiler contract system message, then forward the original
        # request messages unchanged. Existing system messages are preserved.
        logger.debug("litellm_proxy: inject_system_message=true")
        data["messages"] = [system_message, *request_messages]
        return data


proxy_handler_instance = ContextCompilerPreCallHook()
