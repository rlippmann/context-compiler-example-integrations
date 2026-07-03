from pathlib import Path

from fastapi.testclient import TestClient
from typing_extensions import TypedDict

from python.examples.execution_authorization.expense_approval.fastapi.app import (
    create_app,
)
from python.examples.execution_authorization.expense_approval.fastapi.model_approval import (
    ModelApproval,
)


class _ApprovalState(TypedDict):
    version: int
    premise: None
    policies: dict[str, str]


def _approved_claim(_expense_summary: str) -> ModelApproval:
    return ModelApproval(
        decision="approved",
        message="APPROVED: reimburse this expense.",
    )


def _denied_claim(_expense_summary: str) -> ModelApproval:
    return ModelApproval(
        decision="not_approved",
        message="DENIED: do not reimburse this expense.",
    )


def _read_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _create_client(tmp_path: Path) -> tuple[TestClient, Path]:
    artifact_path = tmp_path / "submitted_expenses.jsonl"
    app = create_app(
        artifact_path=artifact_path,
        model_approval_getter=_approved_claim,
    )
    return TestClient(app), artifact_path


def test_baseline_trusts_model_approval_and_writes_one_record(tmp_path: Path) -> None:
    client, artifact_path = _create_client(tmp_path)

    response = client.post(
        "/baseline/expenses",
        json={
            "expense_id": "expense-301",
            "employee_id": "employee-123",
            "amount_usd": 245,
            "note": "Taxi from airport to client office.",
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 200
    assert response.json()["path"] == "baseline"
    assert response.json()["model_decision"] == "approved"
    assert response.json()["agent_claim"] == "Approved by the agent. Reimburse it."
    assert response.json()["executed"] is True
    assert response.json()["side_effect_count"] == 1
    records = _read_jsonl(artifact_path)
    assert len(records) == 1
    assert '"authorization_source": "model_claim"' in records[0]


def test_compiler_path_with_absent_state_returns_403_and_writes_none(
    tmp_path: Path,
) -> None:
    client, artifact_path = _create_client(tmp_path)

    response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-302",
            "employee_id": "employee-456",
            "amount_usd": 180,
            "note": "Hotel Wi-Fi charge.",
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["model_decision"] == "approved"
    assert detail["agent_claim"] == "Approved by the agent. Reimburse it."
    assert detail["authorization_state"] == "blocked"
    assert detail["executed"] is False
    assert detail["blocked_reason"] == "expense_approval state not authorized"
    assert _read_jsonl(artifact_path) == []


def test_compiler_path_with_prohibited_state_returns_403_and_writes_none(
    tmp_path: Path,
) -> None:
    client, artifact_path = _create_client(tmp_path)

    prohibited_state: _ApprovalState = {
        "version": 2,
        "premise": None,
        "policies": {"expense_approval": "prohibit"},
    }
    response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-303",
            "employee_id": "employee-789",
            "amount_usd": 75,
            "note": "Parking near customer site.",
            "authoritative_state": prohibited_state,
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["model_decision"] == "approved"
    assert detail["agent_claim"] == "Approved by the agent. Reimburse it."
    assert detail["authorization_state"] == "blocked"
    assert detail["executed"] is False
    assert _read_jsonl(artifact_path) == []


def test_compiler_path_with_contradictory_directive_returns_conflict_and_writes_none(
    tmp_path: Path,
) -> None:
    client, artifact_path = _create_client(tmp_path)

    authorized_state: _ApprovalState = {
        "version": 2,
        "premise": None,
        "policies": {"expense_approval": "use"},
    }
    response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-304",
            "employee_id": "employee-111",
            "amount_usd": 300,
            "note": "Do not execute on conflict.",
            "authoritative_state": authorized_state,
            "compiler_input": "prohibit expense_approval",
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["model_decision"] == "approved"
    assert detail["agent_claim"] == "Approved by the agent. Reimburse it."
    assert detail["decision_kind"] == "clarify"
    assert detail["authorization_state"] == "blocked"
    assert detail["executed"] is False
    assert "currently in use" in detail["prompt_to_user"]
    assert _read_jsonl(artifact_path) == []


def test_compiler_path_with_authorized_state_executes_and_writes_one_record(
    tmp_path: Path,
) -> None:
    client, artifact_path = _create_client(tmp_path)

    authorized_state: _ApprovalState = {
        "version": 2,
        "premise": None,
        "policies": {"expense_approval": "use"},
    }
    response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-305",
            "employee_id": "employee-222",
            "amount_usd": 320,
            "note": "Conference shuttle reimbursement.",
            "authoritative_state": authorized_state,
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 200
    assert response.json()["path"] == "compiler"
    assert response.json()["model_decision"] == "approved"
    assert response.json()["agent_claim"] == "Approved by the agent. Reimburse it."
    assert response.json()["authorization_state"] == "authorized"
    assert response.json()["executed"] is True
    assert response.json()["side_effect_count"] == 1
    records = _read_jsonl(artifact_path)
    assert len(records) == 1
    assert '"authorization_source": "context_compiler_state"' in records[0]


def test_compiler_path_with_non_approval_claim_and_authorized_state_does_not_execute(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "submitted_expenses.jsonl"
    app = create_app(
        artifact_path=artifact_path,
        model_approval_getter=_denied_claim,
    )
    client = TestClient(app)

    authorized_state: _ApprovalState = {
        "version": 2,
        "premise": None,
        "policies": {"expense_approval": "use"},
    }
    response = client.post(
        "/compiler/expenses",
        json={
            "expense_id": "expense-306",
            "employee_id": "employee-333",
            "amount_usd": 120,
            "note": "Non-approval should still block.",
            "authoritative_state": authorized_state,
            "agent_claim": "Approved by the agent. Reimburse it.",
        },
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["model_decision"] == "not_approved"
    assert detail["agent_claim"] == "Approved by the agent. Reimburse it."
    assert detail["authorization_state"] == "blocked"
    assert detail["blocked_reason"] == "model claim did not approve expense"
    assert _read_jsonl(artifact_path) == []
