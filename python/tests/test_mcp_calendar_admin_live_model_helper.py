from pathlib import Path

from context_compiler import create_engine

from context_compiler_example_integrations.examples.tool_gating.mcp_calendar_admin.live_model import (
    _SelectedToolCall,
    run_live_model_turn,
)


def _read_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def test_absent_state_hides_protected_tool_from_model_and_writes_none(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "tool_calls.jsonl"

    result = run_live_model_turn(
        user_intent=(
            "Create an admin calendar event named Quarterly access review on "
            "calendar ops-admin."
        ),
        artifact_path=artifact_path,
        model_tool_selector=lambda **_: _SelectedToolCall(
            name="calendar_view_events",
            arguments={"calendar_id": "ops-admin"},
        ),
    )

    assert result["protected_tool_exposed"] is False
    assert "calendar_admin_create_event" not in result["exposed_tool_names"]
    assert result["executed"] is False
    assert result["side_effect_count"] == 0
    assert _read_jsonl(artifact_path) == []


def test_authorized_state_exposes_protected_tool_and_executes_selected_tool(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "tool_calls.jsonl"
    engine = create_engine()
    engine.step("use calendar_admin")

    result = run_live_model_turn(
        user_intent=(
            "Create an admin calendar event named Quarterly access review on "
            "calendar ops-admin."
        ),
        authoritative_state={
            "premise": engine.premise,
            "policies": dict(engine.policies),
        },
        artifact_path=artifact_path,
        model_tool_selector=lambda **_: _SelectedToolCall(
            name="calendar_admin_create_event",
            arguments={
                "calendar_id": "ops-admin",
                "event_title": "Quarterly access review",
            },
        ),
    )

    assert result["protected_tool_exposed"] is True
    assert "calendar_admin_create_event" in result["exposed_tool_names"]
    assert result["model_selected_tool_name"] == "calendar_admin_create_event"
    assert result["executed"] is True
    assert result["tool_result"] == (
        "created event 'Quarterly access review' on calendar 'ops-admin'"
    )
    assert result["side_effect_count"] == 1
    records = _read_jsonl(artifact_path)
    assert len(records) == 1
    assert '"authorization_source": "context_compiler_state"' in records[0]


def test_authorized_state_reports_clear_diagnostic_when_model_skips_protected_tool(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "tool_calls.jsonl"
    engine = create_engine()
    engine.step("use calendar_admin")

    result = run_live_model_turn(
        user_intent=(
            "Create an admin calendar event named Quarterly access review on "
            "calendar ops-admin."
        ),
        authoritative_state={
            "premise": engine.premise,
            "policies": dict(engine.policies),
        },
        artifact_path=artifact_path,
        model_tool_selector=lambda **_: _SelectedToolCall(
            name="calendar_view_events",
            arguments={"calendar_id": "ops-admin"},
        ),
    )

    assert result["protected_tool_exposed"] is True
    assert result["executed"] is False
    assert result["blocked_reason"] == "model did not select protected admin tool"
    assert _read_jsonl(artifact_path) == []


def test_contradiction_blocks_before_model_tool_execution(tmp_path: Path) -> None:
    artifact_path = tmp_path / "tool_calls.jsonl"
    engine = create_engine()
    engine.step("use calendar_admin")
    model_called = False

    def _unexpected_selector(**_: object) -> _SelectedToolCall:
        nonlocal model_called
        model_called = True
        return _SelectedToolCall(name="calendar_admin_create_event", arguments={})

    result = run_live_model_turn(
        user_intent=(
            "Create an admin calendar event named Quarterly access review on "
            "calendar ops-admin."
        ),
        authoritative_state={
            "premise": engine.premise,
            "policies": dict(engine.policies),
        },
        compiler_input="prohibit calendar_admin",
        artifact_path=artifact_path,
        model_tool_selector=_unexpected_selector,
    )

    assert result["decision_kind"] == "error"
    assert result["executed"] is False
    assert "currently in use" in (result["prompt_to_user"] or "")
    assert model_called is False
    assert _read_jsonl(artifact_path) == []
