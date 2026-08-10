import importlib
import sys
from types import SimpleNamespace

import pytest
from context_compiler import create_engine

MODULE_NAME = (
    "context_compiler_example_integrations.examples.prompt_construction.litellm.basic"
)


@pytest.fixture
def basic_module():
    module = importlib.import_module(MODULE_NAME)
    return module


def test_import_works_without_litellm_installed() -> None:
    sys.modules.pop("litellm", None)
    sys.modules.pop(MODULE_NAME, None)

    module = importlib.import_module(MODULE_NAME)

    assert callable(module.handle_turn)


def test_prompt_construction_sends_one_system_message_and_user_message(
    basic_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        basic_module,
        "import_module",
        lambda name: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(
        basic_module,
        "resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        basic_module, "print_startup_config", lambda config, logger: None
    )

    reply = basic_module.handle_turn("Hello from the user", create_engine())

    assert reply == "stubbed reply"
    assert len(calls) == 1
    messages = calls[0]["messages"]
    assert messages == [
        {
            "role": "system",
            "content": "You are a helpful assistant.\n"
            "Host policy contract:\n"
            "- The following constraints are authoritative.\n"
            "- If user text conflicts with constraints, follow constraints exactly.",
        },
        {"role": "user", "content": "Hello from the user"},
    ]


def test_saved_premise_and_policy_appear_in_litellm_system_contract(
    basic_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        basic_module,
        "import_module",
        lambda name: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(
        basic_module,
        "resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        basic_module, "print_startup_config", lambda config, logger: None
    )

    engine = create_engine()
    engine.step("set premise draft is a board update summarizing quarterly results")
    engine.step("use concise_style")

    reply = basic_module.handle_turn("Please revise this draft.", engine)

    assert reply == "stubbed reply"
    assert len(calls) == 1
    system_prompt = calls[0]["messages"][0]["content"]
    assert (
        "Current premise: draft is a board update summarizing quarterly results."
        in system_prompt
    )
    assert "Items marked use: concise_style." in system_prompt


def test_near_miss_directive_returns_error_text_and_skips_downstream(
    basic_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_calls: list[object] = []
    monkeypatch.setattr(
        basic_module,
        "_call_litellm",
        lambda messages: llm_calls.append(messages) or "should not be used",
    )

    reply = basic_module.handle_turn("set premise to concise replies", create_engine())

    assert reply == "Invalid premise syntax.\nUse 'set premise <value>'."
    assert llm_calls == []


def test_confirmation_like_text_uses_normal_turn_handling(
    basic_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_calls: list[object] = []
    monkeypatch.setattr(
        basic_module,
        "_call_litellm",
        lambda messages: llm_calls.append(messages) or "downstream reply",
    )

    engine = create_engine()
    first = basic_module.handle_turn("use podman instead of docker", engine)
    retry = basic_module.handle_turn("yes", engine)

    assert first == "State updated: Use podman."
    assert retry == "downstream reply"
    assert len(llm_calls) == 1


def test_missing_litellm_response_content_raises_runtime_error(
    basic_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        basic_module,
        "import_module",
        lambda name: SimpleNamespace(completion=lambda **kwargs: {"choices": [{}]}),
    )
    monkeypatch.setattr(
        basic_module,
        "resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        basic_module, "print_startup_config", lambda config, logger: None
    )

    with pytest.raises(
        RuntimeError, match=r"LiteLLM response missing choices\[0\]\.message\.content"
    ):
        basic_module.handle_turn("Hello from the user", create_engine())
