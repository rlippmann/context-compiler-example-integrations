import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

MODULE_PATH = (
    Path("/Users/rlippmann/Source/context-compiler-example-integrations")
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


def _state(
    *, premise: str | None = None, policies: dict[str, str] | None = None
) -> dict[str, object]:
    return {
        "premise": premise,
        "policies": {} if policies is None else policies,
        "version": 2,
    }


def test_unsupported_call_type_returns_original_data_unchanged(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_unsupported")
    hook = module.ContextCompilerPreCallHook()
    data = {"messages": [{"role": "user", "content": "hello"}], "model": "demo"}

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "embeddings"))

    assert result is data


def test_clarify_result_returns_string_and_does_not_mutate_forwarded_messages(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_clarify")
    hook = module.ContextCompilerPreCallHook()
    original_messages = [{"role": "user", "content": "use kubectl instead of docker"}]
    data = {"model": "demo", "messages": deepcopy(original_messages)}

    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: {
            "kind": "confirm",
            "prompt_to_user": 'Did you mean to use "kubectl" instead?',
        },
    )

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result == 'Did you mean to use "kubectl" instead?'
    assert data["messages"] == original_messages


def test_update_state_path_prepends_exactly_one_compiler_contract_system_message(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_update")
    hook = module.ContextCompilerPreCallHook()
    original_messages = [
        {"role": "system", "content": "original system"},
        {"role": "user", "content": "prohibit peanuts"},
    ]
    data = {"model": "demo", "messages": deepcopy(original_messages)}

    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: {
            "kind": "state",
            "state": _state(policies={"peanuts": "prohibit"}),
        },
    )

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    messages = data["messages"]
    assert len(messages) == len(original_messages) + 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"].count("Host policy contract:") == 1
    assert messages[1:] == original_messages


def test_passthrough_preserves_original_request_messages_after_injected_contract(
    monkeypatch,
) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_passthrough")
    hook = module.ContextCompilerPreCallHook()
    original_messages = [
        {"role": "system", "content": "original system"},
        {"role": "assistant", "content": "earlier reply"},
        {"role": "user", "content": "hello there"},
    ]
    data = {"model": "demo", "messages": deepcopy(original_messages)}

    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: {"kind": "state", "state": _state()},
    )

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "chat_completion"))

    assert result is data
    assert data["messages"][1:] == original_messages
    assert data["messages"][0]["role"] == "system"


def test_mixed_content_extraction_only_replays_user_text_segments(monkeypatch) -> None:
    module = _load_proxy_module(monkeypatch, "litellm_proxy_mixed_content")
    messages = [
        {"role": "system", "content": "system"},
        {"role": "assistant", "content": "assistant text"},
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
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "ignored"}}],
        },
        {"role": "user", "content": {"type": "text", "text": "ignored non-list shape"}},
    ]

    transcript = module._extract_user_transcript(messages)

    assert transcript == [
        {"role": "user", "content": "plain user text"},
        {"role": "user", "content": "alpha beta"},
    ]
