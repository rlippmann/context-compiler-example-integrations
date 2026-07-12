import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT
    / "python"
    / "reference_integrations"
    / "litellm_proxy"
    / "context_compiler_precall_hook.py"
)


def _load_proxy_module(monkeypatch: pytest.MonkeyPatch, module_name: str):
    litellm_mod = types.ModuleType("litellm")
    integrations_mod = types.ModuleType("litellm.integrations")
    custom_logger_mod = types.ModuleType("litellm.integrations.custom_logger")

    class _CustomLogger:
        pass

    custom_logger_mod.CustomLogger = _CustomLogger
    monkeypatch.setitem(sys.modules, "litellm", litellm_mod)
    monkeypatch.setitem(sys.modules, "litellm.integrations", integrations_mod)
    monkeypatch.setitem(
        sys.modules, "litellm.integrations.custom_logger", custom_logger_mod
    )

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unsupported_call_type_returns_original_data_unchanged(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_unsupported")
    hook = module.ContextCompilerPreCallHook()
    data = {"messages": [{"role": "user", "content": "hello"}], "model": "demo"}

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "embeddings"))

    assert result is data


def test_missing_session_key_fails_clearly_in_persistent_mode(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_missing_session")
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "messages": [{"role": "user", "content": "prohibit peanuts"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert isinstance(result, str)
    assert "requires a stable session key" in result


def test_default_mode_is_stateless_and_requires_no_session_key(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_default_stateless")
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "messages": [{"role": "user", "content": "what snack should I bring?"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data


def test_stateless_mode_processes_only_current_turn_and_ignores_earlier_messages(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_stateless")
    hook = module.ContextCompilerPreCallHook()
    original_messages = [
        {"role": "user", "content": "prohibit peanuts"},
        {"role": "assistant", "content": "noted"},
        {"role": "user", "content": "what snack should I bring?"},
    ]
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": deepcopy(original_messages),
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert data["messages"][1:] == original_messages
    assert "peanuts" not in str(data["messages"][0]["content"])


def test_persistent_mode_restores_checkpoint_and_isolates_sessions(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_session_isolation")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHook()

    first = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-a",
        "messages": [{"role": "user", "content": "prohibit peanuts"}],
    }
    second = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-a",
        "messages": [{"role": "user", "content": "what snack should I bring?"}],
    }
    other = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-b",
        "messages": [{"role": "user", "content": "what snack should I bring?"}],
    }

    asyncio.run(hook.async_pre_call_hook(None, None, first, "completion"))
    asyncio.run(hook.async_pre_call_hook(None, None, second, "completion"))
    asyncio.run(hook.async_pre_call_hook(None, None, other, "completion"))

    assert "peanuts" in str(second["messages"][0]["content"])
    assert "peanuts" not in str(other["messages"][0]["content"])


def test_pending_clarification_persists_and_later_confirmation_resolves(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_pending")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHook()

    clarify_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-clarify",
        "messages": [{"role": "user", "content": "use kubectl instead of docker"}],
    }
    confirm_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-clarify",
        "messages": [
            {"role": "user", "content": "use kubectl instead of docker"},
            {"role": "assistant", "content": "question asked"},
            {"role": "user", "content": "yes"},
        ],
    }

    first = asyncio.run(
        hook.async_pre_call_hook(None, None, clarify_data, "completion")
    )
    second = asyncio.run(
        hook.async_pre_call_hook(None, None, confirm_data, "completion")
    )

    assert isinstance(first, str)
    assert "Did you mean" in first
    assert second is confirm_data
    checkpoint = module.CHECKPOINT_STORE.load("chat-clarify")
    assert checkpoint is not None
    assert checkpoint.get("pending") is None


def test_pending_clarification_persists_and_later_rejection_resolves(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_pending_no")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHook()

    clarify_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-clarify-no",
        "messages": [{"role": "user", "content": "use kubectl instead of docker"}],
    }
    reject_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-clarify-no",
        "messages": [
            {"role": "user", "content": "use kubectl instead of docker"},
            {"role": "assistant", "content": "question asked"},
            {"role": "user", "content": "no"},
        ],
    }

    first = asyncio.run(
        hook.async_pre_call_hook(None, None, clarify_data, "completion")
    )
    second = asyncio.run(
        hook.async_pre_call_hook(None, None, reject_data, "completion")
    )

    assert isinstance(first, str)
    assert second is reject_data
    checkpoint = module.CHECKPOINT_STORE.load("chat-clarify-no")
    assert checkpoint is not None
    assert checkpoint.get("pending") is None
    assert "docker" not in str(reject_data["messages"][0]["content"])


def test_checkpoint_is_saved_after_clarify(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_save_after_clarify")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-save-clarify",
        "messages": [{"role": "user", "content": "use kubectl instead of docker"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert isinstance(result, str)
    checkpoint = module.CHECKPOINT_STORE.load("chat-save-clarify")
    assert checkpoint is not None
    assert checkpoint.get("pending") is not None


def test_normal_update_explicitly_saves_checkpoint(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_save_after_update")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-save-update",
        "messages": [{"role": "user", "content": "prohibit peanuts"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    checkpoint = module.CHECKPOINT_STORE.load("chat-save-update")
    assert checkpoint is not None
    assert checkpoint["authoritative_state"]["policies"] == {"peanuts": "prohibit"}
    assert checkpoint.get("pending") is None


def test_current_turn_is_processed_exactly_once(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_step_once")
    hook = module.ContextCompilerPreCallHook()
    seen_inputs: list[str] = []
    original_create_engine = module.create_engine

    def create_engine_with_tracking():
        engine = original_create_engine()
        original_step = engine.step

        def tracked_step(user_input: str):
            seen_inputs.append(user_input)
            return original_step(user_input)

        engine.step = tracked_step
        return engine

    monkeypatch.setattr(module, "create_engine", create_engine_with_tracking)
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [
            {"role": "user", "content": "prohibit peanuts"},
            {"role": "user", "content": "what snack should I bring?"},
        ],
    }

    asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert seen_inputs == ["what snack should I bring?"]


def test_corrupt_checkpoint_fails_clearly(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_corrupt_checkpoint")
    module.CHECKPOINT_STORE.clear()
    module.CHECKPOINT_STORE.save("broken", {"checkpoint_version": 99})
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "broken",
        "messages": [{"role": "user", "content": "hello"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert isinstance(result, str)
    assert "checkpoint load failed" in result


def test_mixed_content_extraction_uses_latest_user_text_segment(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_mixed_content")
    hook = module.ContextCompilerPreCallHook()
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [
            {"role": "user", "content": "plain user text"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "alpha"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.test/image.png"},
                    },
                    {"type": "text", "text": "beta"},
                ],
            },
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert data["messages"][1:] == [
        {"role": "user", "content": "plain user text"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "alpha"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.test/image.png"},
                },
                {"type": "text", "text": "beta"},
            ],
        },
    ]


def test_no_removed_replay_api_remains(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_no_replay")

    assert not hasattr(module, "compile_transcript")
    assert "replay" not in MODULE_PATH.read_text(encoding="utf-8").lower()
