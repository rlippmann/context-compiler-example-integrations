"""Narrow checkpoint/session support for LiteLLM Proxy reference hooks.

This module is intentionally repo-local and small in scope:
- explicit persistent vs stateless mode selection
- explicit session-key resolution
- storage-neutral checkpoint store contract
- latest-user-turn extraction helpers

The in-memory store is suitable only for tests and single-process examples.
It does not provide durability, multi-worker coordination, or atomic updates.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

MODE_PERSISTENT = "persistent"
MODE_STATELESS = "stateless"
SESSION_MODE_ENV_VAR = "CONTEXT_COMPILER_SESSION_MODE"


class CheckpointStore(Protocol):
    def load(self, session_key: str) -> Mapping[str, object] | None: ...

    def save(self, session_key: str, checkpoint: Mapping[str, object]) -> None: ...


class InMemoryCheckpointStore:
    """Single-process example checkpoint store for tests and local reference use."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, dict[str, object]] = {}

    def load(self, session_key: str) -> Mapping[str, object] | None:
        checkpoint = self._checkpoints.get(session_key)
        if checkpoint is None:
            return None
        return dict(checkpoint)

    def save(self, session_key: str, checkpoint: Mapping[str, object]) -> None:
        self._checkpoints[session_key] = dict(checkpoint)

    def clear(self) -> None:
        self._checkpoints.clear()


@dataclass(frozen=True)
class SessionContext:
    mode: str
    session_key: str | None
    source: str | None


def resolve_session_context(data: Mapping[str, object]) -> SessionContext:
    mode = _resolve_mode(data)
    session_key, source = _resolve_session_key(data)
    return SessionContext(mode=mode, session_key=session_key, source=source)


def extract_latest_user_text(messages: list[dict[str, object]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = extract_text_content(message.get("content"))
        if content is not None:
            return content
        return None
    return None


def extract_text_content(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return " ".join(text_parts)
    return None


def checkpoint_to_jsonable(checkpoint_json: str) -> dict[str, object]:
    import json

    raw = json.loads(checkpoint_json)
    if not isinstance(raw, dict):
        raise ValueError("Checkpoint JSON must decode to an object.")
    return raw


def checkpoint_from_jsonable(checkpoint: Mapping[str, object]) -> str:
    import json

    return json.dumps(checkpoint, separators=(",", ":"), sort_keys=True)


def _resolve_mode(data: Mapping[str, object]) -> str:
    candidates = [
        data.get("context_compiler_mode"),
        os.getenv(SESSION_MODE_ENV_VAR),
    ]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip().lower()
        if normalized in {MODE_PERSISTENT, MODE_STATELESS}:
            return normalized
    return MODE_STATELESS


def _resolve_session_key(data: Mapping[str, object]) -> tuple[str | None, str | None]:
    candidates: list[tuple[str, object]] = [
        ("context_compiler_session_key", data.get("context_compiler_session_key")),
        (
            "metadata.context_compiler_session_key",
            _nested_lookup(data.get("metadata"), "context_compiler_session_key"),
        ),
    ]
    for source, value in candidates:
        normalized = _normalize_key(value)
        if normalized is not None:
            return normalized, source
    return None, None


def _nested_lookup(value: object, key: str) -> object:
    if isinstance(value, Mapping):
        return value.get(key)
    return None


def _normalize_key(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
