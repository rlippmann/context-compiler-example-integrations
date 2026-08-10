import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from context_compiler.grammar import decompose_directive
from context_compiler_directive_drafter import NoDirective, UnknownDirective

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT
    / "python"
    / "reference_integrations"
    / "litellm_proxy"
    / "context_compiler_precall_hook_with_directive_drafter.py"
)


def _load_module(monkeypatch: pytest.MonkeyPatch, module_name: str):
    litellm_mod = types.ModuleType("litellm")
    integrations_mod = types.ModuleType("litellm.integrations")
    custom_logger_mod = types.ModuleType("litellm.integrations.custom_logger")

    class _CustomLogger:
        pass

    custom_logger_mod.CustomLogger = _CustomLogger  # type: ignore[attr-defined]
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


def test_drafter_runs_only_for_current_turn(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_current_only")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    drafted_calls: list[tuple[str, dict[str, object]]] = []

    def fake_draft(message: str) -> object:
        drafted_calls.append((message, {}))
        return module.DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module, "_draft_last_user_message", fake_draft)
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [
            {"role": "user", "content": "prohibit peanuts"},
            {"role": "assistant", "content": "noted"},
            {"role": "user", "content": "please use docker"},
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert drafted_calls == [("please use docker", {})]


def test_drafter_output_applies_to_current_turn_only(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_applies")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    directive = decompose_directive("prohibit docker")
    assert directive is not None
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda message: module.DraftResult(
            source="test",
            result=directive,
        ),
    )
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [
            {"role": "user", "content": "prohibit peanuts"},
            {"role": "user", "content": "please use docker"},
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert "docker" in str(data["messages"][0]["content"])
    assert "peanuts" not in str(data["messages"][0]["content"])


def test_persistent_mode_with_drafter_rejects_failed_application_without_persisting(
    monkeypatch,
) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_failed_apply")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    drafted_inputs: list[str] = []

    def fake_draft(message: str) -> object:
        drafted_inputs.append(message)
        return module.DraftResult(
            source="test",
            result=decompose_directive("change premise to formal tone"),
        )

    monkeypatch.setattr(module, "_draft_last_user_message", fake_draft)
    rejected_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-drafter-failed-apply",
        "messages": [{"role": "user", "content": "change premise to formal tone"}],
    }

    result = asyncio.run(
        hook.async_pre_call_hook(None, None, rejected_data, "completion")
    )

    assert isinstance(result, str)
    assert "No premise is set." in result
    assert drafted_inputs == ["change premise to formal tone"]
    assert module.CHECKPOINT_STORE.load("chat-drafter-failed-apply") is None


def test_missing_session_key_fails_clearly_in_persistent_mode(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_missing_session")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "messages": [{"role": "user", "content": "please use docker"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert isinstance(result, str)
    assert "requires a stable session key" in result


def test_default_mode_is_stateless_and_requires_no_session_key(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_default_stateless")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda message: module.DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        ),
    )
    data = {
        "model": "demo",
        "messages": [{"role": "user", "content": "please use docker"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data


def test_stateless_mode_has_no_cross_call_continuity(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_stateless")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda message: module.DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        ),
    )
    first = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [{"role": "user", "content": "prohibit peanuts"}],
    }
    second = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": [{"role": "user", "content": "what snack should I bring?"}],
    }

    asyncio.run(hook.async_pre_call_hook(None, None, first, "completion"))
    second_result = asyncio.run(
        hook.async_pre_call_hook(None, None, second, "completion")
    )

    assert second_result is second
    assert "peanuts" not in str(second["messages"][0]["content"])


def test_persistent_mode_with_drafter_preserves_existing_checkpoint_on_failure(
    monkeypatch,
) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_preserve_checkpoint")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHookWithPreprocessor()

    def seed_draft(message: str) -> object:
        return module.DraftResult(
            source="test",
            result=decompose_directive("use docker"),
        )

    monkeypatch.setattr(module, "_draft_last_user_message", seed_draft)
    seed_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-drafter-preserve-checkpoint",
        "messages": [{"role": "user", "content": "use docker"}],
    }
    rejected_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-drafter-preserve-checkpoint",
        "messages": [{"role": "user", "content": "prohibit docker"}],
    }

    seed_result = asyncio.run(
        hook.async_pre_call_hook(None, None, seed_data, "completion")
    )
    assert seed_result is seed_data

    def reject_draft(message: str) -> object:
        return module.DraftResult(
            source="test",
            result=decompose_directive("prohibit docker"),
        )

    monkeypatch.setattr(module, "_draft_last_user_message", reject_draft)

    result = asyncio.run(
        hook.async_pre_call_hook(None, None, rejected_data, "completion")
    )

    assert isinstance(result, str)
    checkpoint = module.CHECKPOINT_STORE.load("chat-drafter-preserve-checkpoint")
    assert checkpoint is not None
    assert checkpoint["policies"] == {"docker": "use"}

    follow_up_data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-drafter-preserve-checkpoint",
        "messages": [{"role": "user", "content": "prohibit docker"}],
    }

    follow_up_result = asyncio.run(
        hook.async_pre_call_hook(None, None, follow_up_data, "completion")
    )

    assert isinstance(follow_up_result, str)
    assert '"docker" is currently in use.' in follow_up_result


def test_normal_update_explicitly_saves_checkpoint(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_save_after_update")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    directive = decompose_directive("prohibit peanuts")
    assert directive is not None
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda message: module.DraftResult(
            source="test",
            result=directive,
        ),
    )
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-drafter-save-update",
        "messages": [{"role": "user", "content": "please prohibit peanuts"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    checkpoint = module.CHECKPOINT_STORE.load("chat-drafter-save-update")
    assert checkpoint is not None
    assert checkpoint["policies"] == {"peanuts": "prohibit"}


def test_restore_happens_before_drafting(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_restore_first")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    module.CHECKPOINT_STORE.save(
        "chat-restore-first",
        {"premise": None, "policies": {"peanuts": "prohibit"}, "version": 2},
    )
    seen_messages: list[str] = []

    def fake_draft(message: str) -> object:
        seen_messages.append(message)
        return module.DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module, "_draft_last_user_message", fake_draft)
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-restore-first",
        "messages": [{"role": "user", "content": "please use docker"}],
    }

    asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert seen_messages == ["please use docker"]


def test_corrupt_checkpoint_fails_clearly(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_corrupt")
    module.CHECKPOINT_STORE.clear()
    module.CHECKPOINT_STORE.save("broken", {"checkpoint_version": 99})
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "broken",
        "messages": [{"role": "user", "content": "please use docker"}],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert isinstance(result, str)
    assert "checkpoint load failed" in result


def test_forwarded_messages_keep_original_user_prompt_text(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_forwarded_text")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    directive = decompose_directive("use docker")
    assert directive is not None
    original_messages = [
        {"role": "system", "content": "original system"},
        {"role": "user", "content": "please use docker"},
    ]
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda message: module.DraftResult(
            source="test",
            result=directive,
        ),
    )
    data = {
        "model": "demo",
        "context_compiler_mode": "stateless",
        "messages": deepcopy(original_messages),
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "chat_completion"))

    assert result is data
    assert data["messages"][1:] == original_messages


def test_compound_directives_fall_through_to_normal_forwarding_when_not_applied(
    monkeypatch,
) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_compound")
    module.CHECKPOINT_STORE.clear()
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    monkeypatch.setattr(
        module,
        "_draft_last_user_message",
        lambda _message: module.DraftResult(
            source="test",
            result=UnknownDirective(reason="reject.multi_candidate_directive"),
        ),
    )
    data = {
        "model": "demo",
        "context_compiler_mode": "persistent",
        "context_compiler_session_key": "chat-compound",
        "messages": [
            {"role": "user", "content": "please use docker and prohibit peanuts"}
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    checkpoint = module.CHECKPOINT_STORE.load("chat-compound")
    assert checkpoint is not None
    assert checkpoint["policies"] == {}


def test_fallback_returns_raw_candidate_text(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_fallback_directive")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/demo-model")
    monkeypatch.setattr(
        module,
        "_get_litellm_completion",
        lambda: lambda **_: {"choices": [{"message": {"content": "use docker"}}]},
    )

    result = module._llm_fallback_candidate("please use docker")

    assert result == "use docker"


def test_fallback_returns_raw_no_directive_sentinel(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_fallback_none")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/demo-model")
    monkeypatch.setattr(
        module,
        "_get_litellm_completion",
        lambda: lambda **_: {"choices": [{"message": {"content": "<NO_DIRECTIVE>"}}]},
    )

    result = module._llm_fallback_candidate("hello there")

    assert result == "<NO_DIRECTIVE>"


def test_fallback_returns_raw_unknown_candidate_text(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_fallback_unknown")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/demo-model")
    monkeypatch.setattr(
        module,
        "_get_litellm_completion",
        lambda: lambda **_: {"choices": [{"message": {"content": "clear everything"}}]},
    )

    result = module._llm_fallback_candidate("clear everything")

    assert result == "clear everything"


def test_fallback_uses_shared_converter_prompt(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_shared_prompt")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/demo-model")
    seen: dict[str, Any] = {}

    def completion(**kwargs):
        seen.update(kwargs)
        return {"choices": [{"message": {"content": "use docker"}}]}

    monkeypatch.setattr(module, "_get_litellm_completion", lambda: completion)
    monkeypatch.setattr(module, "get_converter_prompt", lambda: "shared prompt")

    result = module._llm_fallback_candidate("please use docker")

    assert result == "use docker"
    assert seen["messages"][0] == {"role": "system", "content": "shared prompt"}


def test_no_removed_replay_api_remains(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_no_replay")

    assert not hasattr(module, "compile_transcript")
    assert "_state_before_last_message" not in MODULE_PATH.read_text(encoding="utf-8")
