"""Minimal host-side execution authorization for expense approval."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from context_compiler import (
    DecisionKind,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    create_engine,
)
from context_compiler.engine import Engine


class ExpenseRequest(TypedDict):
    expense_id: str
    employee_id: str
    amount_usd: int
    note: str


class ExpenseSubmission(TypedDict):
    expense_id: str
    employee_id: str
    amount_usd: int
    note: str


class ExpenseExecutionResult(TypedDict):
    authorization_state: Literal["authorized", "blocked"]
    executed: bool
    blocked_reason: str | None
    submission: ExpenseSubmission | None
    execution_log: list[str]


class ExpenseTurnResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    execution_result: ExpenseExecutionResult


def _decision_kind_name(
    decision: object,
) -> Literal["clarify", "update", "passthrough"]:
    if not isinstance(decision, dict):
        raise ValueError("unexpected decision shape")

    kind = decision.get("kind")
    if kind == DecisionKind.ERROR:
        return "clarify"
    if kind == DecisionKind.UPDATE:
        return "update"
    if kind == DecisionKind.NO_DIRECTIVE:
        return "passthrough"
    raise ValueError(f"unexpected decision kind: {kind}")


@dataclass
class ExpenseHost:
    """Host-owned runtime behavior for expense execution."""

    execution_log: list[str] = field(default_factory=list)

    def submit_expense(self, request: ExpenseRequest) -> ExpenseSubmission:
        self.execution_log.append(f"submitted:{request['expense_id']}")
        return {
            "expense_id": request["expense_id"],
            "employee_id": request["employee_id"],
            "amount_usd": request["amount_usd"],
            "note": request["note"],
        }


def expense_execution_is_authorized(policies: Mapping[str, PolicyValue]) -> bool:
    """Authorize execution only from explicit authoritative compiler state."""

    if policies.get("expense_approval") == POLICY_PROHIBIT:
        return False

    return policies.get("expense_approval") == POLICY_USE


def execute_expense_if_authorized(
    request: ExpenseRequest,
    *,
    policies: Mapping[str, PolicyValue],
    host: ExpenseHost,
) -> ExpenseExecutionResult:
    """Run the host-side action only when authoritative state allows it."""

    if not expense_execution_is_authorized(policies):
        return {
            "authorization_state": "blocked",
            "executed": False,
            "blocked_reason": "expense_approval state not authorized",
            "submission": None,
            "execution_log": host.execution_log.copy(),
        }

    submission = host.submit_expense(request)
    return {
        "authorization_state": "authorized",
        "executed": True,
        "blocked_reason": None,
        "submission": submission,
        "execution_log": host.execution_log.copy(),
    }


def handle_expense_turn(
    engine: Engine,
    *,
    compiler_input: str,
    request: ExpenseRequest,
    host: ExpenseHost,
) -> ExpenseTurnResult:
    """Block execution on clarify and otherwise enforce current authoritative state."""

    decision = engine.step(compiler_input)

    if decision["kind"] == DecisionKind.ERROR:
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision["message"],
            "execution_result": {
                "authorization_state": "blocked",
                "executed": False,
                "blocked_reason": "clarification required before expense execution",
                "submission": None,
                "execution_log": host.execution_log.copy(),
            },
        }

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision["message"],
        "execution_result": execute_expense_if_authorized(
            request,
            policies=engine.policies,
            host=host,
        ),
    }


def run_demo() -> ExpenseExecutionResult:
    """Run a deterministic demonstration with explicit authorization state."""

    engine = create_engine()
    engine.step("use expense_approval")

    request: ExpenseRequest = {
        "expense_id": "expense-100",
        "employee_id": "employee-123",
        "amount_usd": 245,
        "note": "Taxi from airport to client office.",
    }
    host = ExpenseHost()

    return execute_expense_if_authorized(
        request,
        policies=engine.policies,
        host=host,
    )
