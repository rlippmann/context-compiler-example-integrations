import os
from pathlib import Path

import pytest
from context_compiler import create_engine

from python.examples.tool_gating.mcp_calendar_admin.live_model import (
    run_live_model_turn,
)

RUN_LIVE_MODEL_ENV_VAR = "RUN_MCP_CALENDAR_ADMIN_LIVE_MODEL"
USER_INTENT = (
    "Create an admin calendar event named Quarterly access review on calendar "
    "ops-admin."
)

pytestmark = pytest.mark.skipif(
    os.getenv(RUN_LIVE_MODEL_ENV_VAR) != "1",
    reason=(
        "Opt-in MCP calendar-admin live-model validation. "
        f"Set {RUN_LIVE_MODEL_ENV_VAR}=1 to run."
    ),
)


def _read_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def test_live_model_tool_surface_changes_with_authoritative_state(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "tool_calls.jsonl"

    absent_result = run_live_model_turn(
        user_intent=USER_INTENT,
        artifact_path=artifact_path,
    )

    assert absent_result["protected_tool_exposed"] is False
    assert absent_result["executed"] is False
    assert _read_jsonl(artifact_path) == []

    allowed_engine = create_engine()
    allowed_engine.step("use calendar_admin")
    allowed_result = run_live_model_turn(
        user_intent=USER_INTENT,
        authoritative_state=allowed_engine.state,
        artifact_path=artifact_path,
    )

    assert allowed_result["protected_tool_exposed"] is True
    if allowed_result["model_selected_tool_name"] != "calendar_admin_create_event":
        raise AssertionError(
            "Protected tool was exposed but the live model did not select "
            "`calendar_admin_create_event`. "
            f"Selected tool: {allowed_result['model_selected_tool_name']!r}. "
            "This opt-in validation requires the model to exercise the protected "
            "tool path explicitly."
        )
    assert allowed_result["executed"] is True
    assert len(_read_jsonl(artifact_path)) == 1

    clarify_result = run_live_model_turn(
        user_intent=USER_INTENT,
        authoritative_state=allowed_engine.state,
        compiler_input="prohibit calendar_admin",
        artifact_path=artifact_path,
    )

    assert clarify_result["decision_kind"] == "clarify"
    assert clarify_result["executed"] is False
    assert len(_read_jsonl(artifact_path)) == 1
