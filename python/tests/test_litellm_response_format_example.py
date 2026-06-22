from types import SimpleNamespace

import pytest
from context_compiler import create_engine

from python.examples.schema_selection.litellm_response_format.response_format import (
    ACTION_PLAN_RESPONSE_FORMAT,
    COMPACT_SUMMARY_RESPONSE_FORMAT,
    optional_litellm_call,
    plan_turn,
)


def test_no_matching_policy_selects_no_response_format() -> None:
    plan = plan_turn("Summarize this.", create_engine())

    assert plan["decision_kind"] == "passthrough"
    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_use_compact_summary_selects_compact_summary_response_format() -> None:
    engine = create_engine()
    engine.step("use compact_summary")

    plan = plan_turn("Summarize this.", engine)

    assert plan["selected_response_format_item"] == "compact_summary"
    assert plan["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT


def test_use_action_plan_selects_action_plan_response_format() -> None:
    engine = create_engine()
    engine.step("use action_plan")

    plan = plan_turn("What should I do next?", engine)

    assert plan["selected_response_format_item"] == "action_plan"
    assert plan["response_format"] == ACTION_PLAN_RESPONSE_FORMAT


def test_prohibit_compact_summary_selects_no_response_format() -> None:
    engine = create_engine()
    engine.step("prohibit compact_summary")

    plan = plan_turn("Summarize this.", engine)

    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_contradiction_clarify_path_selects_no_schema() -> None:
    engine = create_engine()
    engine.step("use compact_summary")

    plan = plan_turn("prohibit compact_summary", engine)

    assert plan["decision_kind"] == "clarify"
    assert plan["selected_response_format_item"] is None
    assert plan["response_format"] is None


def test_optional_litellm_call_preserves_selected_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format._get_litellm_completion",
        lambda: fake_completion,
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(
        user_input="Summarize this.",
        response_format=COMPACT_SUMMARY_RESPONSE_FORMAT,
    )

    assert reply == "stubbed reply"
    assert calls[0]["response_format"] == COMPACT_SUMMARY_RESPONSE_FORMAT


def test_optional_litellm_call_omits_response_format_when_none_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "stubbed reply"}}]}

    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format._get_litellm_completion",
        lambda: fake_completion,
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.resolve_provider_config",
        lambda default_model: SimpleNamespace(
            model=default_model,
            base_url="https://example.invalid/v1",
            api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        "python.examples.schema_selection.litellm_response_format.response_format.print_startup_config",
        lambda config: None,
    )

    reply = optional_litellm_call(user_input="Summarize this.", response_format=None)

    assert reply == "stubbed reply"
    assert "response_format" not in calls[0]
