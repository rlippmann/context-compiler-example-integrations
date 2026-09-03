import json
import sys
import types
from types import SimpleNamespace

from context_compiler_directive_drafter.fallbacks.litellm import (
    create_litellm_fallback,
)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_structured_litellm_fallback_sends_schema_and_parses_response(monkeypatch):
    calls: list[dict[str, object]] = []
    litellm = types.ModuleType("litellm")
    litellm.supports_response_schema = lambda **_: True  # type: ignore[attr-defined]

    def completion(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return _response(
            json.dumps({"classification": "directive", "output": "use docker"})
        )

    litellm.completion = completion  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", litellm)

    fallback = create_litellm_fallback("openai/demo-model")

    assert fallback("please use docker") == "use docker"
    assert calls[0]["model"] == "openai/demo-model"
    assert calls[0]["response_format"]["type"] == "json_schema"  # type: ignore[index]


def test_free_text_litellm_fallback_probes_and_uses_sentinel(monkeypatch):
    calls: list[dict[str, object]] = []
    litellm = types.ModuleType("litellm")
    litellm.supports_response_schema = lambda **_: False  # type: ignore[attr-defined]

    def completion(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("response_format is not supported")
        return _response("use docker")

    litellm.completion = completion  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", litellm)

    fallback = create_litellm_fallback("ollama/demo-model")

    assert fallback("please use docker") == "use docker"
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]
