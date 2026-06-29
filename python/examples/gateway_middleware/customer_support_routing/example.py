"""Minimal host-side gateway middleware for customer support routing."""

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


class SupportRequest(TypedDict):
    request_id: str
    customer_id: str
    queue_hint: str
    message: str


class RoutedRequest(TypedDict):
    request_id: str
    customer_id: str
    queue: Literal["general_support", "billing_support"]
    message: str


class GatewayResult(TypedDict):
    gateway_decision: Literal["forwarded", "blocked", "defaulted"]
    routed_queue: Literal["general_support", "billing_support"] | None
    blocked_reason: str | None
    downstream_called: bool
    downstream_response: str | None
    gateway_log: list[str]
    downstream_log: list[str]


class GatewayTurnResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    gateway_result: GatewayResult


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
class SupportService:
    """Downstream handler that the gateway may or may not call."""

    downstream_log: list[str] = field(default_factory=list)

    def handle(self, request: RoutedRequest) -> str:
        self.downstream_log.append(
            f"handled:{request['queue']}:{request['request_id']}"
        )
        return f"{request['queue']} handled {request['request_id']}"


@dataclass
class SupportGateway:
    """Host-owned gateway boundary and routing behavior."""

    gateway_log: list[str] = field(default_factory=list)

    def forward(
        self,
        request: SupportRequest,
        *,
        queue: Literal["general_support", "billing_support"],
        gateway_decision: Literal["forwarded", "defaulted"] = "forwarded",
        downstream: SupportService,
    ) -> GatewayResult:
        self.gateway_log.append(f"{gateway_decision}:{queue}:{request['request_id']}")
        routed_request: RoutedRequest = {
            "request_id": request["request_id"],
            "customer_id": request["customer_id"],
            "queue": queue,
            "message": request["message"],
        }
        downstream_response = downstream.handle(routed_request)
        return {
            "gateway_decision": gateway_decision,
            "routed_queue": queue,
            "blocked_reason": None,
            "downstream_called": True,
            "downstream_response": downstream_response,
            "gateway_log": self.gateway_log.copy(),
            "downstream_log": downstream.downstream_log.copy(),
        }

    def block(self, request: SupportRequest, *, reason: str) -> GatewayResult:
        self.gateway_log.append(f"blocked:{request['request_id']}")
        return {
            "gateway_decision": "blocked",
            "routed_queue": None,
            "blocked_reason": reason,
            "downstream_called": False,
            "downstream_response": None,
            "gateway_log": self.gateway_log.copy(),
            "downstream_log": [],
        }


def billing_support_is_allowed(state: State) -> bool:
    """Allow billing support only from explicit authoritative compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))

    if "billing_support" in prohibit_items:
        return False

    return "billing_support" in use_items


def route_support_request(
    request: SupportRequest,
    *,
    state: State,
    gateway: SupportGateway,
    downstream: SupportService,
) -> GatewayResult:
    """Make the gateway decision before any downstream call."""

    if request["queue_hint"] != "billing_support":
        return gateway.forward(
            request,
            queue="general_support",
            gateway_decision="defaulted",
            downstream=downstream,
        )

    if not billing_support_is_allowed(state):
        return gateway.block(
            request,
            reason="billing_support state not authorized",
        )

    return gateway.forward(
        request,
        queue="billing_support",
        downstream=downstream,
    )


def handle_gateway_turn(
    engine: Engine,
    *,
    compiler_input: str,
    request: SupportRequest,
    gateway: SupportGateway,
    downstream: SupportService,
) -> GatewayTurnResult:
    """Block routing changes on clarify and otherwise enforce authoritative state."""

    decision = engine.step(compiler_input)

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "gateway_result": gateway.block(
                request,
                reason="clarification required before gateway routing",
            ),
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "gateway_result": route_support_request(
            request,
            state=authoritative_state,
            gateway=gateway,
            downstream=downstream,
        ),
    }


def run_demo() -> GatewayResult:
    """Run a deterministic gateway demonstration with explicit policy state."""

    engine = create_engine()
    engine.step("use billing_support")

    request: SupportRequest = {
        "request_id": "support-100",
        "customer_id": "customer-123",
        "queue_hint": "billing_support",
        "message": "Need help correcting an invoice charge.",
    }
    gateway = SupportGateway()
    downstream = SupportService()

    return route_support_request(
        request,
        state=engine.state,
        gateway=gateway,
        downstream=downstream,
    )
