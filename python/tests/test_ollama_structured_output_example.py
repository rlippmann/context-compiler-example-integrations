import json
from io import BytesIO

import pytest
from context_compiler import create_engine

from python.examples.schema_selection.ollama_structured_output.example import (
    PYTHON_SCRIPT_SCHEMA,
    optional_ollama_call,
    plan_turn,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_use_python_script_selects_python_script_schema() -> None:
    engine = create_engine()
    engine.step("use python_script")

    plan = plan_turn("Write a helper script.", engine)

    assert plan["selected_schema_item"] == "python_script"
    assert plan["format_schema"] == PYTHON_SCRIPT_SCHEMA


def test_prohibited_competing_schema_not_selected() -> None:
    engine = create_engine()
    engine.step("use python_script")
    engine.step("prohibit shell_command")

    plan = plan_turn("Write a helper script.", engine)

    assert plan["selected_schema_item"] == "python_script"
    assert plan["format_schema"] == PYTHON_SCRIPT_SCHEMA


def test_empty_or_unknown_state_selects_no_schema() -> None:
    empty_plan = plan_turn("Write something.", create_engine())

    unknown_engine = create_engine()
    unknown_engine.step("use compact_summary")
    unknown_plan = plan_turn("Write something.", unknown_engine)

    assert empty_plan["selected_schema_item"] is None
    assert empty_plan["format_schema"] is None
    assert unknown_plan["selected_schema_item"] is None
    assert unknown_plan["format_schema"] is None


def test_contradiction_clarify_path_selects_no_schema() -> None:
    engine = create_engine()
    engine.step("use python_script")

    plan = plan_turn("prohibit python_script", engine)

    assert plan["decision_kind"] == "clarify"
    assert plan["selected_schema_item"] is None
    assert plan["format_schema"] is None


def test_optional_ollama_call_includes_format_when_schema_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):
        captured_payloads.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse({"message": {"content": "stubbed"}})

    monkeypatch.setattr(
        "python.examples.schema_selection.ollama_structured_output.example.urllib.request.urlopen",
        fake_urlopen,
    )

    response = optional_ollama_call(
        user_input="Write a helper script.",
        model="llama3.1",
        format_schema=PYTHON_SCRIPT_SCHEMA,
    )

    assert response == {"message": {"content": "stubbed"}}
    assert captured_payloads[0]["format"] == PYTHON_SCRIPT_SCHEMA


def test_optional_ollama_call_omits_format_when_schema_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):
        captured_payloads.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse({"message": {"content": "stubbed"}})

    monkeypatch.setattr(
        "python.examples.schema_selection.ollama_structured_output.example.urllib.request.urlopen",
        fake_urlopen,
    )

    response = optional_ollama_call(
        user_input="Write a helper script.",
        model="llama3.1",
        format_schema=None,
    )

    assert response == {"message": {"content": "stubbed"}}
    assert "format" not in captured_payloads[0]
