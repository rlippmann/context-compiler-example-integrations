"""FastAPI comparison demo for execution authorization with expense approval."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from context_compiler import State, create_engine, get_decision_state, is_clarify
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing_extensions import TypedDict

from python.examples.execution_authorization.expense_approval.example import (
    expense_execution_is_authorized,
)

from .model_approval import ModelApproval, get_model_approval_claim


class ExpenseRequest(BaseModel):
    expense_id: str
    employee_id: str
    amount_usd: int
    note: str
    authoritative_state: dict[str, object] | None = None
    compiler_input: str = ""
    agent_claim: str | None = None


class SideEffectRecord(TypedDict):
    expense_id: str
    employee_id: str
    amount_usd: int
    note: str
    path: Literal["baseline", "compiler"]
    model_decision: str
    authorization_source: Literal["model_claim", "context_compiler_state"]


class ExpenseMutationResponse(TypedDict):
    path: Literal["baseline", "compiler"]
    decision_kind: Literal["clarify", "update", "passthrough"] | None
    model_decision: str
    model_message: str
    agent_claim: str | None
    authorization_state: Literal["authorized", "blocked"]
    executed: bool
    blocked_reason: str | None
    prompt_to_user: str | None
    submission: dict[str, str | int] | None
    side_effect_path: str
    side_effect_count: int


def _decision_kind_name(
    decision: object,
) -> Literal["clarify", "update", "passthrough"]:
    if not isinstance(decision, dict):
        raise ValueError("unexpected decision shape")

    kind = decision.get("kind")
    kind_name = getattr(kind, "value", None)
    if kind_name not in {"clarify", "update", "passthrough"}:
        raise ValueError(f"unexpected decision kind: {kind_name}")

    return kind_name


def _state_for_request(authoritative_state: dict[str, object] | None) -> State | None:
    if authoritative_state is None:
        return None
    return cast(State, authoritative_state)


def _expense_summary(request: ExpenseRequest) -> str:
    return (
        f"expense_id={request.expense_id}; "
        f"employee_id={request.employee_id}; "
        f"amount_usd={request.amount_usd}; "
        f"note={request.note}"
    )


@dataclass
class ExpenseSideEffectStore:
    """Host-owned append-only side-effect artifact for the comparison demo."""

    artifact_path: Path

    def append(
        self,
        *,
        request: ExpenseRequest,
        path_name: Literal["baseline", "compiler"],
        model_decision: str,
        authorization_source: Literal["model_claim", "context_compiler_state"],
    ) -> dict[str, str | int]:
        record: SideEffectRecord = {
            "expense_id": request.expense_id,
            "employee_id": request.employee_id,
            "amount_usd": request.amount_usd,
            "note": request.note,
            "path": path_name,
            "model_decision": model_decision,
            "authorization_source": authorization_source,
        }
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with self.artifact_path.open("a", encoding="utf-8") as artifact:
            artifact.write(json.dumps(record, sort_keys=True) + "\n")
        return {
            "expense_id": request.expense_id,
            "employee_id": request.employee_id,
            "amount_usd": request.amount_usd,
            "note": request.note,
        }

    def count(self) -> int:
        if not self.artifact_path.exists():
            return 0
        with self.artifact_path.open(encoding="utf-8") as artifact:
            return sum(1 for _ in artifact)


def _blocked_response(
    *,
    path_name: Literal["baseline", "compiler"],
    model_claim: ModelApproval,
    side_effect_store: ExpenseSideEffectStore,
    blocked_reason: str,
    prompt_to_user: str | None,
    decision_kind: Literal["clarify", "update", "passthrough"] | None,
    request_agent_claim: str | None,
) -> ExpenseMutationResponse:
    return {
        "path": path_name,
        "decision_kind": decision_kind,
        "model_decision": model_claim.decision,
        "model_message": model_claim.message,
        "agent_claim": request_agent_claim,
        "authorization_state": "blocked",
        "executed": False,
        "blocked_reason": blocked_reason,
        "prompt_to_user": prompt_to_user,
        "submission": None,
        "side_effect_path": str(side_effect_store.artifact_path),
        "side_effect_count": side_effect_store.count(),
    }


def _authorized_response(
    *,
    path_name: Literal["baseline", "compiler"],
    model_claim: ModelApproval,
    side_effect_store: ExpenseSideEffectStore,
    submission: dict[str, str | int],
    decision_kind: Literal["clarify", "update", "passthrough"] | None,
    request_agent_claim: str | None,
) -> ExpenseMutationResponse:
    return {
        "path": path_name,
        "decision_kind": decision_kind,
        "model_decision": model_claim.decision,
        "model_message": model_claim.message,
        "agent_claim": request_agent_claim,
        "authorization_state": "authorized",
        "executed": True,
        "blocked_reason": None,
        "prompt_to_user": None,
        "submission": submission,
        "side_effect_path": str(side_effect_store.artifact_path),
        "side_effect_count": side_effect_store.count(),
    }


def create_app(
    *,
    artifact_path: Path | None = None,
    model_approval_getter: Callable[[str], ModelApproval] = get_model_approval_claim,
) -> FastAPI:
    if artifact_path is None:
        artifact_path = Path(
            "/tmp/context_compiler_expense_approval/submitted_expenses.jsonl"
        )

    side_effect_store = ExpenseSideEffectStore(artifact_path=artifact_path)
    app = FastAPI(title="expense-approval-fastapi-comparison")
    app.state.side_effect_store = side_effect_store

    @app.post("/baseline/expenses")
    def submit_baseline_expense(request: ExpenseRequest) -> ExpenseMutationResponse:
        model_claim = model_approval_getter(_expense_summary(request))
        if not model_claim.is_approved:
            raise HTTPException(
                status_code=403,
                detail=_blocked_response(
                    path_name="baseline",
                    model_claim=model_claim,
                    side_effect_store=side_effect_store,
                    blocked_reason="model claim did not approve expense",
                    prompt_to_user=None,
                    decision_kind=None,
                    request_agent_claim=request.agent_claim,
                ),
            )

        submission = side_effect_store.append(
            request=request,
            path_name="baseline",
            model_decision=model_claim.decision,
            authorization_source="model_claim",
        )
        return _authorized_response(
            path_name="baseline",
            model_claim=model_claim,
            side_effect_store=side_effect_store,
            submission=submission,
            decision_kind=None,
            request_agent_claim=request.agent_claim,
        )

    @app.post("/compiler/expenses")
    def submit_compiler_mediated_expense(
        request: ExpenseRequest,
    ) -> ExpenseMutationResponse:
        model_claim = model_approval_getter(_expense_summary(request))
        if not model_claim.is_approved:
            raise HTTPException(
                status_code=403,
                detail=_blocked_response(
                    path_name="compiler",
                    model_claim=model_claim,
                    side_effect_store=side_effect_store,
                    blocked_reason="model claim did not approve expense",
                    prompt_to_user=None,
                    decision_kind=None,
                    request_agent_claim=request.agent_claim,
                ),
            )

        engine = create_engine(state=_state_for_request(request.authoritative_state))
        decision_kind: Literal["clarify", "update", "passthrough"] | None = None
        prompt_to_user: str | None = None
        authoritative_state = engine.state

        if request.compiler_input:
            decision = engine.step(request.compiler_input)
            decision_kind = _decision_kind_name(decision)
            prompt_to_user = decision.get("prompt_to_user")
            if is_clarify(decision):
                raise HTTPException(
                    status_code=409,
                    detail=_blocked_response(
                        path_name="compiler",
                        model_claim=model_claim,
                        side_effect_store=side_effect_store,
                        blocked_reason=(
                            "clarification required before expense execution"
                        ),
                        prompt_to_user=prompt_to_user,
                        decision_kind=decision_kind,
                        request_agent_claim=request.agent_claim,
                    ),
                )

            decision_state = get_decision_state(decision)
            authoritative_state = (
                decision_state if decision_state is not None else engine.state
            )

        if not expense_execution_is_authorized(authoritative_state):
            raise HTTPException(
                status_code=403,
                detail=_blocked_response(
                    path_name="compiler",
                    model_claim=model_claim,
                    side_effect_store=side_effect_store,
                    blocked_reason="expense_approval state not authorized",
                    prompt_to_user=prompt_to_user,
                    decision_kind=decision_kind,
                    request_agent_claim=request.agent_claim,
                ),
            )

        submission = side_effect_store.append(
            request=request,
            path_name="compiler",
            model_decision=model_claim.decision,
            authorization_source="context_compiler_state",
        )
        return _authorized_response(
            path_name="compiler",
            model_claim=model_claim,
            side_effect_store=side_effect_store,
            submission=submission,
            decision_kind=decision_kind,
            request_agent_claim=request.agent_claim,
        )

    return app


app = create_app()


if __name__ == "__main__":
    print(
        "Run with: uv run fastapi dev "
        "python/examples/execution_authorization/expense_approval/fastapi/app.py"
    )
