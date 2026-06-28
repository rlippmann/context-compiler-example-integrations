"""Minimal host-side schema selection for refund intake."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from context_compiler import POLICY_USE, State, create_engine, get_policy_items


class IntakeRequest(TypedDict):
    customer_id: str
    message: str


class RefundIntakeResult(TypedDict):
    kind: Literal["refund"]
    customer_id: str
    reason: str


class TechnicalSupportResult(TypedDict):
    kind: Literal["technical_support"]
    customer_id: str
    issue: str


class IntakeRunResult(TypedDict):
    selected_schema: str | None
    refund_handler_called: bool
    technical_support_handler_called: bool
    result: RefundIntakeResult | TechnicalSupportResult | None


@dataclass
class IntakeHandler:
    name: str
    called: bool = False

    def handle(
        self, request: IntakeRequest
    ) -> RefundIntakeResult | TechnicalSupportResult:
        self.called = True

        if self.name == "refund_intake":
            return {
                "kind": "refund",
                "customer_id": request["customer_id"],
                "reason": request["message"],
            }

        if self.name == "technical_support":
            return {
                "kind": "technical_support",
                "customer_id": request["customer_id"],
                "issue": request["message"],
            }

        raise ValueError(f"unknown handler: {self.name}")


def select_schema_from_state(state: State) -> str | None:
    """Select a host-side workflow from authoritative state."""

    use_items = set(get_policy_items(state, POLICY_USE))

    if "refund_intake" in use_items:
        return "refund_intake"

    if "technical_support" in use_items:
        return "technical_support"

    return None


def run_intake(
    request: IntakeRequest,
    *,
    selected_schema: str | None,
    refund_handler: IntakeHandler,
    technical_support_handler: IntakeHandler,
) -> RefundIntakeResult | TechnicalSupportResult | None:
    """Dispatch to the selected host-side handler, if any."""

    if selected_schema == "refund_intake":
        return refund_handler.handle(request)

    if selected_schema == "technical_support":
        return technical_support_handler.handle(request)

    return None


def run_demo() -> IntakeRunResult:
    """Run a small demonstration with refund_intake enabled."""

    engine = create_engine()
    engine.step("use refund_intake")

    request: IntakeRequest = {
        "customer_id": "customer-123",
        "message": "I need a refund for order A-100.",
    }

    refund_handler = IntakeHandler("refund_intake")
    technical_support_handler = IntakeHandler("technical_support")

    selected_schema = select_schema_from_state(engine.state)
    result = run_intake(
        request,
        selected_schema=selected_schema,
        refund_handler=refund_handler,
        technical_support_handler=technical_support_handler,
    )

    return {
        "selected_schema": selected_schema,
        "refund_handler_called": refund_handler.called,
        "technical_support_handler_called": technical_support_handler.called,
        "result": result,
    }
