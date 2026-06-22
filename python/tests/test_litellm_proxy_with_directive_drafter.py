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
    / "context_compiler_precall_hook_with_directive_drafter.py"
)


def _load_module(monkeypatch: pytest.MonkeyPatch, module_name: str):
    litellm_mod = types.ModuleType("litellm")
    integrations_mod = types.ModuleType("litellm.integrations")
    custom_logger_mod = types.ModuleType("litellm.integrations.custom_logger")

    class _CustomLogger:
        pass

    custom_logger_mod.CustomLogger = _CustomLogger
    monkeypatch.setitem(sys.modules, "litellm", litellm_mod)
    monkeypatch.setitem(sys.modules, "litellm.integrations", integrations_mod)
    monkeypatch.setitem(sys.modules, "litellm.integrations.custom_logger", custom_logger_mod)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(*, premise: str | None = None, policies: dict[str, str] | None = None) -> dict[str, object]:
    return {"premise": premise, "policies": {} if policies is None else policies, "version": 2}


def test_latest_user_message_is_drafted_before_transcript_replay(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_latest")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    compile_calls: list[list[dict[str, str]]] = []

    def compile_transcript(transcript):
        compile_calls.append(transcript)
        if len(compile_calls) == 1:
            return {"kind": "state", "state": _state()}
        return {"kind": "state", "state": _state(policies={"docker": "use"})}

    monkeypatch.setattr(module, "compile_transcript", compile_transcript)
    monkeypatch.setattr(module, "_preprocess_last_user_message", lambda message, state: "use docker")

    data = {
        "model": "demo",
        "messages": [
            {"role": "user", "content": "hello there"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "please use docker"},
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert compile_calls == [
        [{"role": "user", "content": "hello there"}],
        [
            {"role": "user", "content": "hello there"},
            {"role": "user", "content": "use docker"},
        ],
    ]


def test_clarify_result_returns_string_and_does_not_forward(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_clarify")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    original_messages = [{"role": "user", "content": "please use docker"}]
    data = {"model": "demo", "messages": deepcopy(original_messages)}

    monkeypatch.setattr(module, "_preprocess_last_user_message", lambda message, state: "use docker")
    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: {"kind": "confirm", "prompt_to_user": 'Did you mean to use "docker" instead?'},
    )

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result == 'Did you mean to use "docker" instead?'
    assert data["messages"] == original_messages


def test_fallback_to_raw_input_path_preserves_host_behavior(monkeypatch) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_raw")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    compile_calls: list[list[dict[str, str]]] = []

    monkeypatch.setattr(module, "_preprocess_last_user_message", lambda message, state: None)
    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: compile_calls.append(transcript) or {"kind": "state", "state": _state()},
    )

    data = {
        "model": "demo",
        "messages": [
            {"role": "user", "content": "first user turn"},
            {"role": "assistant", "content": "assistant reply"},
            {"role": "user", "content": "please use docker"},
        ],
    }

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))

    assert result is data
    assert compile_calls == [
        [{"role": "user", "content": "first user turn"}],
        [
            {"role": "user", "content": "first user turn"},
            {"role": "user", "content": "please use docker"},
        ],
    ]


def test_forwarded_messages_receive_exactly_one_contract_system_message_when_continuing(
    monkeypatch,
) -> None:
    module = _load_module(monkeypatch, "litellm_proxy_with_drafter_contract")
    hook = module.ContextCompilerPreCallHookWithPreprocessor()
    original_messages = [
        {"role": "system", "content": "original system"},
        {"role": "assistant", "content": "earlier reply"},
        {"role": "user", "content": "hello there"},
    ]
    data = {"model": "demo", "messages": deepcopy(original_messages)}

    monkeypatch.setattr(module, "_preprocess_last_user_message", lambda message, state: None)
    monkeypatch.setattr(
        module,
        "compile_transcript",
        lambda transcript: {"kind": "state", "state": _state(policies={"docker": "use"})},
    )

    result = asyncio.run(hook.async_pre_call_hook(None, None, data, "chat_completion"))

    assert result is data
    system_messages = [message for message in data["messages"] if message.get("role") == "system"]
    contract_messages = [
        message for message in system_messages if "Host policy contract:" in str(message.get("content"))
    ]
    assert len(contract_messages) == 1
    assert data["messages"][1:] == original_messages
