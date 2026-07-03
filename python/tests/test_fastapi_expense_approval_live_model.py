import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from python.examples.execution_authorization.expense_approval.fastapi.app import (
    create_app,
)

RUN_LIVE_MODEL_ENV_VAR = "RUN_EXPENSE_APPROVAL_LIVE_MODEL"

pytestmark = pytest.mark.skipif(
    os.getenv(RUN_LIVE_MODEL_ENV_VAR) != "1",
    reason=(
        "Opt-in expense-approval live-model validation. "
        f"Set {RUN_LIVE_MODEL_ENV_VAR}=1 to run."
    ),
)


def _read_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def test_live_model_comparison_shows_model_approval_is_not_authorization(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "submitted_expenses.jsonl"
    client = TestClient(create_app(artifact_path=artifact_path))

    baseline_response = client.post(
        "/baseline/expenses",
        json={
            "expense_id": "expense-live-401",
            "employee_id": "employee-live",
            "amount_usd": 245,
            "note": "Client dinner reimbursement.",
        },
    )

    assert baseline_response.status_code == 200
    assert baseline_response.json()["model_decision"] == "approved"
    assert baseline_response.json()["executed"] is True
    assert len(_read_jsonl(artifact_path)) == 1

    compiler_response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-live-402",
            "employee_id": "employee-live",
            "amount_usd": 245,
            "note": "Client dinner reimbursement.",
        },
    )

    assert compiler_response.status_code == 403
    detail = compiler_response.json()["detail"]
    assert detail["model_decision"] == "approved"
    assert detail["authorization_state"] == "blocked"
    assert detail["executed"] is False
    assert len(_read_jsonl(artifact_path)) == 1

    authorized_compiler_response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-live-403",
            "employee_id": "employee-live",
            "amount_usd": 245,
            "note": "Client dinner reimbursement.",
            "authoritative_state": {
                "version": 2,
                "premise": None,
                "policies": {"expense_approval": "use"},
            },
        },
    )

    assert authorized_compiler_response.status_code == 200
    assert authorized_compiler_response.json()["model_decision"] == "approved"
    assert authorized_compiler_response.json()["authorization_state"] == "authorized"
    assert authorized_compiler_response.json()["executed"] is True
    assert len(_read_jsonl(artifact_path)) == 2
