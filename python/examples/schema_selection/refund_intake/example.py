"""Minimal host-side schema selection for refund intake."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypedDict

from context_compiler import (
    POLICY_USE,
    PolicyValue,
    Engine,
)

DAMAGED_ORDER_PREMISE = (
    "order A-100 is a delivered physical item reported as damaged on arrival"
)
DIGITAL_LOGIN_FAILURE_PREMISE = (
    "order A-100 is a digital subscription with an active login failure after purchase"
)


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


OrderIntakeContext = Literal[
    "damaged_physical_delivery", "digital_subscription_login_failure"
]


class IntakeRunResult(TypedDict):
    selected_schema: str | None
    refund_handler_called: bool
    technical_support_handler_called: bool
    result: RefundIntakeResult | TechnicalSupportResult | None


_SCHEMA_BY_ORDER_INTAKE_CONTEXT: dict[OrderIntakeContext, str] = {
    "damaged_physical_delivery": "refund_intake",
    "digital_subscription_login_failure": "technical_support",
}


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


def classify_premise_as_order_intake_context(
    premise: str | None,
) -> OrderIntakeContext | None:
    """Map saved order facts to a host-owned intake context."""

    if premise is None:
        return None

    normalized_premise = premise.casefold()
    if (
        "delivered physical item" in normalized_premise
        and "damaged on arrival" in normalized_premise
    ):
        return "damaged_physical_delivery"

    if (
        "digital subscription" in normalized_premise
        and "login failure" in normalized_premise
    ):
        return "digital_subscription_login_failure"

    return None


def select_schema_from_order_intake_context(
    context: OrderIntakeContext | None,
) -> str | None:
    """Map a host-owned intake context to the selected schema."""

    if context is None:
        return None

    return _SCHEMA_BY_ORDER_INTAKE_CONTEXT[context]


def select_schema_from_semantics(
    *, premise: str | None, policies: Mapping[str, PolicyValue]
) -> str | None:
    """Select a host-side workflow from authoritative state."""

    if policies.get("refund_intake") == POLICY_USE:
        return "refund_intake"

    if policies.get("technical_support") == POLICY_USE:
        return "technical_support"

    intake_context = classify_premise_as_order_intake_context(premise)
    return select_schema_from_order_intake_context(intake_context)


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

    engine = Engine()
    engine.step("use refund_intake")

    request: IntakeRequest = {
        "customer_id": "customer-123",
        "message": "I need a refund for order A-100.",
    }

    refund_handler = IntakeHandler("refund_intake")
    technical_support_handler = IntakeHandler("technical_support")

    selected_schema = select_schema_from_semantics(
        premise=engine.premise,
        policies=engine.policies,
    )
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
