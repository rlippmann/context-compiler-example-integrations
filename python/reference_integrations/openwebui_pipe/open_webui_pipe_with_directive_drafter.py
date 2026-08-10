"""
title: Context Compiler Open WebUI Pipe (Directive Drafter)
author: rlippmann
author_url: https://github.com/rlippmann/context-compiler-example-integrations
version: 0.9.4
requirements: context-compiler>=0.8.3, context-compiler-directive-drafter>=0.1.2

Open WebUI integration with Context Compiler directive drafter.

This example extends `open_webui_pipe.py` by inserting a directive-drafting step:

1. Run heuristic directive drafter (fast, high-precision cases)
2. Fall back to Open WebUI-native model completion when needed
3. Pass resulting directive (or original input) to `engine.step(...)`

Core decision handling remains the same as the base integration.
Failed transitions are rejected for the current request and do not leave
resumable in-memory engine state behind.
"""

import inspect
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict, cast

from fastapi import Request  # type: ignore[import-not-found]
from open_webui.models.users import Users  # type: ignore[import-not-found]
from open_webui.utils.chat import generate_chat_completion  # type: ignore[import-not-found]
from open_webui.utils.models import get_all_models  # type: ignore[import-not-found]

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    # Keep this import optional: CI/tests run without integration extras.
    # These lightweight fallbacks keep import-time behavior deterministic so
    # coverage exercises the pipe module without pydantic installed.
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs: object) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(*, default: Any, description: str = "") -> Any:  # type: ignore[no-redef]
        del description
        return default


from context_compiler import (
    DecisionKind,
    DECISION_UPDATE,
    POLICY_PROHIBIT,
    POLICY_USE,
    create_engine,
    is_update,
    PolicyValue,
)
from context_compiler.engine import Engine
from context_compiler.grammar import CanonicalDirective
from context_compiler_directive_drafter import (
    DirectiveDrafter,
    DraftResult,
    NoDirective,
    UnknownDirective,
    get_converter_prompt,
)

logger = logging.getLogger(__name__)

_CC_MARKER = "[[cc_state]]"
_ENGINES_BY_CHAT_KEY: dict[str, Engine] = {}


class _EngineSnapshot(TypedDict):
    premise: str | None
    policies: dict[str, PolicyValue]


def _resolve_chat_key(
    user: dict[str, Any],
    chat_id: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    if chat_id:
        return chat_id
    if isinstance(metadata, dict):
        metadata_chat_id = metadata.get("chat_id")
        if isinstance(metadata_chat_id, str) and metadata_chat_id:
            return metadata_chat_id
    user_id = str(user["id"])
    return f"no-chat-id:{user_id}"


def _extract_latest_user_text(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        return None
    return None


def _snapshot_engine_state(engine: Engine) -> _EngineSnapshot:
    return {"premise": engine.premise, "policies": dict(engine.policies)}


def _restore_engine_from_snapshot(snapshot_json: str) -> Engine:
    engine = create_engine()
    engine.import_json(snapshot_json)
    return engine


def _render_compiler_state_block(engine: Engine) -> str:
    lines: list[str] = [_CC_MARKER]

    if engine.premise is not None:
        lines.append(f"Premise: {engine.premise}")

    use_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_USE
    )
    if use_items:
        lines.append("Use: " + ", ".join(use_items))

    prohibit_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_PROHIBIT
    )
    if prohibit_items:
        lines.append("Prohibit: " + ", ".join(prohibit_items))

    return "\n".join(lines)


def _render_show_state_summary(engine: Engine) -> str:
    use_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_USE
    )
    prohibit_items = sorted(
        key for key, value in engine.policies.items() if value == POLICY_PROHIBIT
    )

    use_text = ", ".join(use_items) if use_items else "none"
    prohibit_text = ", ".join(prohibit_items) if prohibit_items else "none"
    premise_text = engine.premise if engine.premise is not None else "none"

    return f"Premise: {premise_text}\nUse: {use_text}\nProhibit: {prohibit_text}"


def _replace_compiler_system_message(
    messages: list[dict[str, Any]],
    rendered_state_block: str,
) -> list[dict[str, Any]]:
    filtered_messages: list[dict[str, Any]] = []
    last_system_index = -1

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if (
            role == "system"
            and isinstance(content, str)
            and content.startswith(_CC_MARKER)
        ):
            continue

        filtered_messages.append(message)
        if role == "system":
            last_system_index = len(filtered_messages) - 1

    insert_at = last_system_index + 1 if last_system_index >= 0 else 0
    compiler_message: dict[str, Any] = {
        "role": "system",
        "content": rendered_state_block,
    }
    return [
        *filtered_messages[:insert_at],
        compiler_message,
        *filtered_messages[insert_at:],
    ]


def _normalize_state(value: object) -> _EngineSnapshot:
    if not isinstance(value, dict):
        return {"premise": None, "policies": {}}
    premise = value.get("premise")
    raw_policies = value.get("policies")
    policies = raw_policies if isinstance(raw_policies, dict) else {}
    normalized_policies = {
        key: value
        for key, value in policies.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    return {
        "premise": premise if isinstance(premise, str) else None,
        "policies": cast(dict[str, PolicyValue], normalized_policies),
    }


def _has_non_empty_authoritative_state(engine: Engine) -> bool:
    if engine.premise is not None:
        return True
    return bool(engine.policies)


def _render_state_summary_line(state: object) -> str:
    typed_state = _normalize_state(state)
    premise = typed_state["premise"]
    use_items = sorted(
        key for key, value in typed_state["policies"].items() if value == POLICY_USE
    )
    prohibit_items = sorted(
        key
        for key, value in typed_state["policies"].items()
        if value == POLICY_PROHIBIT
    )
    return (
        f"premise={premise if premise is not None else '(none)'}; "
        f"use={', '.join(use_items) if use_items else '(none)'}; "
        f"prohibit={', '.join(prohibit_items) if prohibit_items else '(none)'}"
    )


def _build_compact_trace_text(
    *,
    decision: object,
    state_before: object,
    state_after: object,
    llm_called: bool,
    state_injected: str,
) -> str:
    kind = decision.get("kind", "unknown") if isinstance(decision, dict) else "unknown"
    changed = (
        "yes"
        if _normalize_state(state_before) != _normalize_state(state_after)
        else "no"
    )
    return "\n".join(
        [
            "Context Compiler trace",
            f"- decision: {kind}",
            f"- llm_called: {'yes' if llm_called else 'no'}",
            f"- state_changed: {changed}",
            f"- state_injected: {state_injected}",
            f"- state_before: {_render_state_summary_line(state_before)}",
            f"- state_after: {_render_state_summary_line(state_after)}",
        ]
    )


def _strip_trace_block_from_text(content: str) -> str:
    marker = "Context Compiler trace"
    index = content.find(marker)
    if index < 0:
        return content
    return content[:index].rstrip()


def _strip_trace_blocks_from_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for message in messages:
        msg = dict(message)
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = _strip_trace_block_from_text(content)
        cleaned.append(msg)
    return cleaned


def _build_forward_messages(
    raw_messages: object,
    *,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Build forwarded messages with trace stripping and optional state injection."""
    messages = (
        _strip_trace_blocks_from_messages(
            [msg for msg in raw_messages if isinstance(msg, dict)]
        )
        if isinstance(raw_messages, list)
        else []
    )
    if engine is not None and _has_non_empty_authoritative_state(engine):
        return _replace_compiler_system_message(
            messages,
            _render_compiler_state_block(engine),
        )
    return messages


def _strip_existing_trace_from_chunk(chunk: object) -> object:
    if isinstance(chunk, str):
        return _strip_trace_block_from_text(chunk)
    if isinstance(chunk, bytes):
        decoded = chunk.decode("utf-8", errors="ignore")
        cleaned = _strip_trace_block_from_text(decoded)
        return cleaned.encode("utf-8")
    return chunk


def _render_item_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _extract_completion_content(response: object) -> str | None:
    choices_attr = getattr(response, "choices", None)
    if isinstance(choices_attr, list) and choices_attr:
        first_choice = choices_attr[0]
        message_attr = getattr(first_choice, "message", None)
        content_attr = getattr(message_attr, "content", None)
        if isinstance(content_attr, str):
            return content_attr

    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

    return None


def _normalize_model_id(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _is_truthy_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "on"}:
            return True
        if normalized in {"false", "0", "off"}:
            return False
    return False


class Pipe:
    """Map Context Compiler decisions into Open WebUI pipe behavior.

    This variant adds a directive-drafter stage before ``engine.step(...)``:
    heuristic first, then Open WebUI-native LLM fallback.
    Update decisions return deterministic local acknowledgement (no model call).
    """

    class Valves(BaseModel):
        BASE_MODEL_ID: str = Field(
            default="",
            description=(
                "Required Open WebUI model id used for forwarding. Must exactly match a "
                "configured model id in Open WebUI (not arbitrary text), for example: "
                "llama3.1:8b."
            ),
        )
        PREPROCESSOR_MODEL_ID: str | None = Field(
            default=None,
            description=(
                "Optional model id for fallback drafting (defaults to BASE_MODEL_ID)."
            ),
        )
        PREPROCESSOR_PROMPT_PROFILE: Literal["default", "llama"] = Field(
            default="default",
            description="Prompt profile for LLM fallback drafting.",
        )
        ALLOW_MISSING_BASE_MODEL_FOR_DEBUG: bool = Field(
            default=False,
            description="Allow missing BASE_MODEL_ID for debug/testing only.",
        )
        SHOW_CONTEXT_COMPILER_TRACE: bool = Field(
            default=False,
            description="Include concise Context Compiler trace text in responses.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self._last_preprocessor_error: str | None = None

    def _allow_missing_base_model_for_debug(self) -> bool:
        return _is_truthy_bool(
            getattr(self.valves, "ALLOW_MISSING_BASE_MODEL_FOR_DEBUG", False)
        )

    def _trace_enabled(self) -> bool:
        return bool(getattr(self.valves, "SHOW_CONTEXT_COMPILER_TRACE", False))

    def _append_trace_to_response(self, response: Any, trace_text: str) -> Any:
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None and callable(
            getattr(body_iterator, "__aiter__", None)
        ):
            response.body_iterator = self._append_trace_to_stream(
                cast(AsyncIterator[object], body_iterator), trace_text
            )
            return response
        aiter = getattr(response, "__aiter__", None)
        if callable(aiter):
            return self._append_trace_to_stream(
                cast(AsyncIterator[object], response), trace_text
            )
        if isinstance(response, str):
            cleaned = _strip_trace_block_from_text(response)
            return f"{cleaned}\n\n{trace_text}"
        if isinstance(response, dict):
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str):
                            cleaned = _strip_trace_block_from_text(content)
                            message["content"] = f"{cleaned}\n\n{trace_text}"
                            return response
        choices_attr = getattr(response, "choices", None)
        if isinstance(choices_attr, list) and choices_attr:
            first_choice = choices_attr[0]
            message_attr = getattr(first_choice, "message", None)
            content_attr = getattr(message_attr, "content", None)
            if message_attr is not None and isinstance(content_attr, str):
                cleaned = _strip_trace_block_from_text(content_attr)
                message_attr.content = f"{cleaned}\n\n{trace_text}"
                return response
        return response

    def _append_trace_to_stream(
        self, stream: AsyncIterator[object], trace_text: str
    ) -> AsyncIterator[object]:
        async def _wrapped() -> AsyncIterator[object]:
            chunk_type: type[str] | type[bytes] | None = None
            saw_done = False
            trace_json = json.dumps(
                {"choices": [{"delta": {"content": f"\n\n{trace_text}"}}]}
            )
            trace_event = f"data: {trace_json}\n\n"

            def _matches_done(value: str) -> bool:
                normalized = value.strip()
                return normalized == "data: [DONE]" or normalized == "[DONE]"

            async for chunk in stream:
                if chunk_type is None:
                    if isinstance(chunk, bytes):
                        chunk_type = bytes
                    elif isinstance(chunk, str):
                        chunk_type = str
                if isinstance(chunk, bytes):
                    decoded = chunk.decode("utf-8", errors="ignore")
                    if _matches_done(decoded):
                        saw_done = True
                        yield trace_event.encode("utf-8")
                        yield chunk
                        continue
                elif isinstance(chunk, str) and _matches_done(chunk):
                    saw_done = True
                    yield trace_event
                    yield chunk
                    continue
                yield _strip_existing_trace_from_chunk(chunk)
            if saw_done:
                return
            suffix = f"\n\n{trace_text}"
            if chunk_type is bytes:
                yield suffix.encode("utf-8")
            else:
                yield suffix

        return _wrapped()

    def _with_trace(
        self,
        response: Any,
        *,
        original_input: str,
        compiler_input: str,
        decision: object,
        state_before: object,
        state_after: object,
        llm_called: bool,
        preprocessor_output: str | None = None,
        state_injected: str = "no",
    ) -> Any:
        if not self._trace_enabled():
            return response
        del original_input, compiler_input, preprocessor_output
        trace_text = _build_compact_trace_text(
            decision=decision,
            state_before=state_before,
            state_after=state_after,
            llm_called=llm_called,
            state_injected=state_injected,
        )
        return self._append_trace_to_response(response, trace_text)

    def _is_model_not_found_text(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        return "model not found" in value.lower()

    def _contains_model_not_found(self, value: object) -> bool:
        if self._is_model_not_found_text(value):
            return True
        if isinstance(value, dict):
            return any(self._contains_model_not_found(v) for v in value.values())
        if isinstance(value, list):
            return any(self._contains_model_not_found(v) for v in value)
        return False

    def _normalize_forward_error(self, response: Any) -> str | None:
        if self._contains_model_not_found(response):
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID is invalid or not "
                "configured in Open WebUI. Configure a valid model id in "
                "Admin Panel → Settings → Models."
            )
        return None

    def _normalize_forward_exception(self, exc: Exception) -> str | None:
        detail = getattr(exc, "detail", None)
        if self._contains_model_not_found(detail) or self._contains_model_not_found(
            str(exc)
        ):
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID is invalid or not "
                "configured in Open WebUI. Configure a valid model id in "
                "Admin Panel → Settings → Models."
            )
        return None

    def _normalize_preprocessor_error(self, response: Any) -> str | None:
        if self._contains_model_not_found(response):
            return (
                "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID is invalid or "
                "not configured in Open WebUI. Configure a valid model id in "
                "Admin Panel → Settings → Models."
            )
        return None

    def _normalize_preprocessor_exception(self, exc: Exception) -> str | None:
        detail = getattr(exc, "detail", None)
        if self._contains_model_not_found(detail) or self._contains_model_not_found(
            str(exc)
        ):
            return (
                "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID is invalid or "
                "not configured in Open WebUI. Configure a valid model id in "
                "Admin Panel → Settings → Models."
            )
        return None

    def _resolve_preprocessor_model_id(self, base_model_id: str | None) -> str | None:
        preprocessor_model_id = _normalize_model_id(self.valves.PREPROCESSOR_MODEL_ID)
        return preprocessor_model_id or base_model_id

    async def _validate_configured_model_ids(
        self,
        request: Request,
        user_payload: dict[str, Any],
        *,
        base_model_id: str | None,
        preprocessor_model_id: str | None,
    ) -> str | None:
        base_model_id = _normalize_model_id(base_model_id)
        preprocessor_model_id = _normalize_model_id(preprocessor_model_id)
        # Best-effort preflight: fail closed only for clear missing-model mismatches.
        # If model discovery fails, preserve runtime behavior and rely on call-path
        # normalization below.
        user = Users.get_user_by_id(user_payload["id"])
        if inspect.isawaitable(user):
            user = await user
        try:
            models = await get_all_models(request, user=user)
        except Exception:
            return None

        known_model_ids: set[str] = set()
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, dict):
                    continue
                model_id = model.get("id")
                if isinstance(model_id, str):
                    known_model_ids.add(model_id)

        if base_model_id and base_model_id not in known_model_ids:
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID was not found "
                "in Open WebUI models."
            )
        if preprocessor_model_id and preprocessor_model_id not in known_model_ids:
            return (
                "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID was not found "
                "in Open WebUI models."
            )
        return None

    async def _llm_fallback_candidate(
        self,
        message: str,
        *,
        request: Request,
        user_payload: dict[str, Any],
        model_id: str | None,
    ) -> str | None:
        self._last_preprocessor_error = None
        model_id = _normalize_model_id(model_id)
        if model_id is None:
            return None

        payload: dict[str, Any] = {
            "model": model_id,
            "stream": False,
            "messages": [
                {"role": "system", "content": get_converter_prompt()},
                {"role": "user", "content": message},
            ],
        }
        user = Users.get_user_by_id(user_payload["id"])
        if inspect.isawaitable(user):
            user = await user
        try:
            response = await generate_chat_completion(request, payload, user)
        except Exception as exc:
            normalized_exception = self._normalize_preprocessor_exception(exc)
            if normalized_exception is not None:
                self._last_preprocessor_error = normalized_exception
                logger.warning("preprocessor: %s", normalized_exception)
            return None

        normalized_error = self._normalize_preprocessor_error(response)
        if normalized_error is not None:
            self._last_preprocessor_error = normalized_error
            logger.warning("preprocessor: %s", normalized_error)
            return None

        return _extract_completion_content(response)

    async def _draft_user_input(
        self,
        message: str,
        *,
        request: Request,
        user_payload: dict[str, Any],
        model_id: str | None,
    ) -> DraftResult:
        async def fallback(candidate_message: str) -> str | None:
            return await self._llm_fallback_candidate(
                candidate_message,
                request=request,
                user_payload=user_payload,
                model_id=model_id,
            )

        drafter = DirectiveDrafter(
            async_fallback=fallback,
            async_fallback_source="openwebui_fallback",
        )
        return await drafter.async_draft_directive(message)

    def _extract_drafted_text(self, drafted_result: DraftResult) -> str | None:
        if isinstance(drafted_result.result, CanonicalDirective):
            return drafted_result.result.text
        if isinstance(drafted_result.result, NoDirective):
            return None
        if isinstance(drafted_result.result, UnknownDirective):
            return None
        return None

    async def _preprocess_user_input(
        self,
        message: str,
        *,
        request: Request,
        user_payload: dict[str, Any],
        prompt_profile: str,
        model_id: str | None,
    ) -> tuple[DraftResult, str | None]:
        del prompt_profile
        self._last_preprocessor_error = None
        drafted_result = await self._draft_user_input(
            message,
            request=request,
            user_payload=user_payload,
            model_id=model_id,
        )
        return drafted_result, self._last_preprocessor_error

    async def _forward_passthrough(
        self,
        body: dict[str, Any],
        user_payload: dict[str, Any],
        request: Request,
        *,
        base_model_id: str | None,
        engine: Engine | None = None,
    ) -> Any:
        if base_model_id is None:
            if self._allow_missing_base_model_for_debug():
                return (
                    "Context Compiler debug mode: BASE_MODEL_ID is empty; "
                    "skipping model passthrough."
                )
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID is required "
                "(or set ALLOW_MISSING_BASE_MODEL_FOR_DEBUG=true for testing)."
            )
        payload = {**body}
        payload["model"] = base_model_id
        payload["messages"] = _build_forward_messages(
            body.get("messages"), engine=engine
        )
        user = Users.get_user_by_id(user_payload["id"])
        if inspect.isawaitable(user):
            user = await user
        try:
            response = await generate_chat_completion(request, payload, user)
        except Exception as exc:
            normalized_exception = self._normalize_forward_exception(exc)
            if normalized_exception is not None:
                return normalized_exception
            raise
        normalized_error = self._normalize_forward_error(response)
        if normalized_error is not None:
            return normalized_error
        return response

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any],
        __request__: Request,
        __chat_id__: str | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> Any:
        # Open WebUI integration entrypoint:
        # 1) extract latest user input
        # 2) run preprocess (heuristic -> LLM fallback)
        # 3) pass directive or original input to engine.step(...)
        # 4) map decision back to Open WebUI response behavior
        raw_messages = body.get("messages")
        messages = (
            [msg for msg in raw_messages if isinstance(msg, dict)]
            if isinstance(raw_messages, list)
            else []
        )
        base_model_id = _normalize_model_id(self.valves.BASE_MODEL_ID)
        preprocessor_model_id = _normalize_model_id(self.valves.PREPROCESSOR_MODEL_ID)
        effective_preprocessor_model = preprocessor_model_id or base_model_id
        current_model_id = str(body.get("model", "")).strip()

        if not base_model_id and not self._allow_missing_base_model_for_debug():
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID is required "
                "(or set ALLOW_MISSING_BASE_MODEL_FOR_DEBUG=true for testing)."
            )
        if base_model_id and current_model_id and base_model_id == current_model_id:
            return (
                "Context Compiler pipe misconfigured: BASE_MODEL_ID must not match "
                "the selected pipe model id to avoid recursive routing."
            )
        if (
            effective_preprocessor_model
            and current_model_id
            and effective_preprocessor_model == current_model_id
        ):
            return (
                "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID must not "
                "match the selected pipe model id to avoid recursive routing."
            )

        preflight_error = await self._validate_configured_model_ids(
            __request__,
            __user__,
            base_model_id=base_model_id,
            preprocessor_model_id=effective_preprocessor_model,
        )
        if preflight_error is not None:
            return preflight_error

        latest_user_text = _extract_latest_user_text(messages)
        logger.debug("preprocessor: user_input_found=%s", latest_user_text is not None)

        if latest_user_text is None:
            return await self._forward_passthrough(
                body,
                __user__,
                __request__,
                base_model_id=base_model_id,
            )

        chat_key = _resolve_chat_key(__user__, __chat_id__, __metadata__)
        engine = _ENGINES_BY_CHAT_KEY.get(chat_key)
        if engine is None:
            engine = create_engine()
            _ENGINES_BY_CHAT_KEY[chat_key] = engine

        if latest_user_text.strip().lower() == "show state":
            return _render_show_state_summary(engine)

        state_before = _snapshot_engine_state(engine)
        preprocess_error: str | None = None
        drafted_result, preprocess_error = await self._preprocess_user_input(
            latest_user_text,
            request=__request__,
            user_payload=__user__,
            prompt_profile=self.valves.PREPROCESSOR_PROMPT_PROFILE,
            model_id=effective_preprocessor_model,
        )
        if preprocess_error is not None:
            return preprocess_error

        logger.debug("preprocessor: drafted_result=%r", drafted_result)
        if not isinstance(drafted_result.result, CanonicalDirective):
            state_injected = (
                "yes" if _has_non_empty_authoritative_state(engine) else "no"
            )
            response = await self._forward_passthrough(
                body,
                __user__,
                __request__,
                base_model_id=base_model_id,
                engine=engine,
            )
            return self._with_trace(
                response,
                original_input=latest_user_text,
                compiler_input=latest_user_text,
                decision={"kind": DecisionKind.NO_DIRECTIVE.value, "message": None},
                state_before=state_before,
                state_after=state_before,
                preprocessor_output=None,
                llm_called=base_model_id is not None,
                state_injected=state_injected,
            )

        engine_snapshot_json = engine.export_json()
        compile_input = drafted_result.result.text
        logger.debug("preprocessor: engine_input=%r", compile_input)
        decision = engine.step(compile_input)
        if decision["kind"] == DecisionKind.ERROR:
            kind = DecisionKind.ERROR.value
        elif is_update(decision):
            kind = DECISION_UPDATE
        else:
            kind = DecisionKind.NO_DIRECTIVE.value
        logger.debug("preprocessor: decision=%s", kind)
        state_after = _snapshot_engine_state(engine)

        if decision["kind"] == DecisionKind.ERROR:
            _ENGINES_BY_CHAT_KEY[chat_key] = _restore_engine_from_snapshot(
                engine_snapshot_json
            )
            return self._with_trace(
                decision["message"] or "",
                original_input=latest_user_text,
                compiler_input=compile_input,
                decision=decision,
                state_before=state_before,
                state_after=state_after,
                preprocessor_output=compile_input,
                llm_called=False,
            )
        if decision["kind"] == DecisionKind.NO_DIRECTIVE:
            state_injected = (
                "yes" if _has_non_empty_authoritative_state(engine) else "no"
            )
            response = await self._forward_passthrough(
                body,
                __user__,
                __request__,
                base_model_id=base_model_id,
                engine=engine,
            )
            return self._with_trace(
                response,
                original_input=latest_user_text,
                compiler_input=compile_input,
                decision=decision,
                state_before=state_before,
                state_after=state_after,
                preprocessor_output=compile_input,
                llm_called=base_model_id is not None,
                state_injected=state_injected,
            )
        if is_update(decision):
            return self._with_trace(
                "State updated.",
                original_input=latest_user_text,
                compiler_input=compile_input,
                decision=decision,
                state_before=state_before,
                state_after=state_after,
                preprocessor_output=compile_input,
                llm_called=False,
            )

        state_injected = "yes" if _has_non_empty_authoritative_state(engine) else "no"
        response = await self._forward_passthrough(
            body,
            __user__,
            __request__,
            base_model_id=base_model_id,
            engine=engine,
        )
        return self._with_trace(
            response,
            original_input=latest_user_text,
            compiler_input=compile_input,
            decision=decision,
            state_before=state_before,
            state_after=state_after,
            preprocessor_output=compile_input,
            llm_called=base_model_id is not None,
            state_injected=state_injected,
        )
