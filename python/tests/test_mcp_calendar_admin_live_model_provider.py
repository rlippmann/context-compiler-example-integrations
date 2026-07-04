from types import SimpleNamespace

import pytest

from host_support.provider_mode import ProviderConfig
from python.examples._shared.litellm_request import build_litellm_provider_kwargs
from python.examples.tool_gating.mcp_calendar_admin import live_model as module


def test_build_litellm_provider_kwargs_prefixes_bare_ollama_model() -> None:
    config = ProviderConfig(
        mode="ollama",
        source="PROVIDER",
        base_url="http://localhost:11434",
        model="qwen2.5:1.5b-instruct",
        api_key=None,
    )

    assert build_litellm_provider_kwargs(config)["model"] == (
        "ollama/qwen2.5:1.5b-instruct"
    )


def test_build_litellm_provider_kwargs_preserves_prefixed_ollama_model() -> None:
    config = ProviderConfig(
        mode="ollama",
        source="PROVIDER",
        base_url="http://localhost:11434",
        model="ollama/qwen2.5:1.5b-instruct",
        api_key=None,
    )

    assert build_litellm_provider_kwargs(config)["model"] == (
        "ollama/qwen2.5:1.5b-instruct"
    )


def test_call_live_model_uses_normalized_ollama_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "calendar_admin_create_event",
                                    "arguments": (
                                        '{"calendar_id":"ops-admin",'
                                        '"event_title":"Quarterly access review"}'
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(
        module,
        "import_module",
        lambda name: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(
        module,
        "resolve_provider_config",
        lambda default_model: SimpleNamespace(
            mode="ollama",
            model="qwen2.5:1.5b-instruct",
            base_url="http://127.0.0.1:11434",
            api_key=None,
        ),
    )
    monkeypatch.setattr(module, "print_startup_config", lambda config: None)
    monkeypatch.setenv("PROVIDER", "ollama")

    selected = module._call_live_model(
        user_intent="Create the admin event.",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "calendar_admin_create_event",
                    "description": "Create an event.",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    assert selected.name == "calendar_admin_create_event"
    assert calls[0]["model"] == "ollama/qwen2.5:1.5b-instruct"
    assert calls[0]["temperature"] == 0
    assert calls[0]["drop_params"] is True


def test_build_litellm_provider_kwargs_keeps_temperature_for_gpt5() -> None:
    config = ProviderConfig(
        mode="openai",
        source="PROVIDER",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key="test-key",
    )

    kwargs = build_litellm_provider_kwargs(config)

    assert kwargs["temperature"] == 0
    assert kwargs["drop_params"] is True


def test_build_litellm_provider_kwargs_keeps_temperature_for_gpt4o_mini() -> None:
    config = ProviderConfig(
        mode="openai",
        source="PROVIDER",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="test-key",
    )

    kwargs = build_litellm_provider_kwargs(config)

    assert kwargs["temperature"] == 0
    assert kwargs["drop_params"] is True


def test_build_litellm_provider_kwargs_keeps_temperature_for_ollama() -> None:
    config = ProviderConfig(
        mode="ollama",
        source="PROVIDER",
        base_url="http://localhost:11434",
        model="qwen2.5:1.5b-instruct",
        api_key=None,
    )

    kwargs = build_litellm_provider_kwargs(config)

    assert kwargs["temperature"] == 0
    assert kwargs["drop_params"] is True


def test_call_live_model_passes_temperature_and_drop_params_for_gpt5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"choices": [{"message": {"tool_calls": []}}]}

    monkeypatch.setattr(
        module,
        "import_module",
        lambda name: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(
        module,
        "resolve_provider_config",
        lambda default_model: SimpleNamespace(
            mode="openai",
            model="gpt-5-mini",
            base_url="https://api.openai.com/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(module, "print_startup_config", lambda config: None)
    monkeypatch.delenv("PROVIDER", raising=False)

    selected = module._call_live_model(
        user_intent="Create the admin event.",
        tools=[],
    )

    assert selected.name is None
    assert calls[0]["model"] == "gpt-5-mini"
    assert calls[0]["temperature"] == 0
    assert calls[0]["drop_params"] is True
