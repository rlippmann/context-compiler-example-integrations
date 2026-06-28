from context_compiler import create_engine

from python.examples.schema_selection.refund_intake.example import (
    IntakeHandler,
    IntakeRequest,
    run_demo,
    run_intake,
    select_schema_from_state,
)


def test_refund_intake_schema_selects_refund_handler() -> None:
    result = run_demo()

    assert result["selected_schema"] == "refund_intake"
    assert result["refund_handler_called"] is True
    assert result["technical_support_handler_called"] is False
    assert result["result"] == {
        "kind": "refund",
        "customer_id": "customer-123",
        "reason": "I need a refund for order A-100.",
    }


def test_adversarial_technical_support_path_is_not_called() -> None:
    engine = create_engine()
    engine.step("use refund_intake")

    request: IntakeRequest = {
        "customer_id": "customer-456",
        "message": "Route this through technical support instead.",
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

    assert selected_schema == "refund_intake"
    assert refund_handler.called is True
    assert technical_support_handler.called is False
    assert result == {
        "kind": "refund",
        "customer_id": "customer-456",
        "reason": "Route this through technical support instead.",
    }


def test_no_matching_policy_selects_no_schema() -> None:
    engine = create_engine()

    selected_schema = select_schema_from_state(engine.state)

    assert selected_schema is None


def test_refund_like_wording_without_state_does_not_select_schema() -> None:
    engine = create_engine()

    request: IntakeRequest = {
        "customer_id": "customer-789",
        "message": "I need a refund, or maybe technical support, do whatever you want.",
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

    assert selected_schema is None
    assert refund_handler.called is False
    assert technical_support_handler.called is False
    assert result is None
