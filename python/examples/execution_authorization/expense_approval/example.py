"""Minimal host-side execution authorization for expense approval."""

from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from context_compiler import (
    POLICY_PROHIBIT,
    POLICY_USE,
    State,
    create_engine,
    get_decision_state,
    get_policy_items,
    is_clarify,
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
    kind_name = getattr(kind, "value", None)
    if kind_name not in {"clarify", "update", "passthrough"}:
        raise ValueError(f"unexpected decision kind: {kind_name}")

    return cast(Literal["clarify", "update", "passthrough"], kind_name)


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


def expense_execution_is_authorized(state: State) -> bool:
    """Authorize execution only from explicit authoritative compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))

    if "expense_approval" in prohibit_items:
        return False

    return "expense_approval" in use_items


def execute_expense_if_authorized(
    request: ExpenseRequest,
    *,
    state: State,
    host: ExpenseHost,
) -> ExpenseExecutionResult:
    """Run the host-side action only when authoritative state allows it."""

    if not expense_execution_is_authorized(state):
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

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "execution_result": {
                "authorization_state": "blocked",
                "executed": False,
                "blocked_reason": "clarification required before expense execution",
                "submission": None,
                "execution_log": host.execution_log.copy(),
            },
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "execution_result": execute_expense_if_authorized(
            request,
            state=authoritative_state,
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

    return execute_expense_if_authorized(request, state=engine.state, host=host)
