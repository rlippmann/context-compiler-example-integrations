from context_compiler import create_engine

from python.examples.checkpoint_continuation.example import (
    BookingHost,
    CheckpointStore,
    continue_itinerary_change,
    initiate_itinerary_change,
    restore_engine_from_authoritative_state_only,
    restore_engine_from_checkpoint,
    run_demo,
    select_itinerary_from_state,
)


def test_checkpoint_export_while_confirmation_is_pending() -> None:
    engine = create_engine()

    result = initiate_itinerary_change(
        engine,
        current_itinerary="boston_trip",
        requested_itinerary="chicago_trip",
    )
    checkpoint = engine.export_checkpoint()

    assert result["decision_kind"] == "clarify"
    assert result["checkpoint_pending"] is True
    assert result["host_applied_change"] is False
    assert result["active_itinerary"] == "boston_trip"
    assert checkpoint["authoritative_state"]["policies"] == {}
    assert checkpoint["pending"] == {
        "kind": "replacement",
        "replacement": {
            "kind": "use_only",
            "new_item": "chicago_trip",
            "old_item": None,
        },
        "prompt_to_user": 'Did you mean to use "chicago_trip" instead?',
    }


def test_restore_into_fresh_engine_and_confirm_applies_change() -> None:
    checkpoint_store = CheckpointStore()
    first_engine = create_engine()
    first_host = BookingHost(
        booking={"booking_id": "booking-101", "active_itinerary": "boston_trip"}
    )

    initiate_itinerary_change(
        first_engine,
        current_itinerary=first_host.booking["active_itinerary"],
        requested_itinerary="chicago_trip",
    )
    checkpoint_store.save(first_engine.export_checkpoint())

    resumed_engine = restore_engine_from_checkpoint(checkpoint_store.load())
    resumed_host = BookingHost(booking=first_host.booking.copy())
    result = continue_itinerary_change(resumed_engine, resumed_host, "yes")

    assert result["decision_kind"] == "update"
    assert result["checkpoint_pending"] is False
    assert result["host_applied_change"] is True
    assert result["active_itinerary"] == "chicago_trip"
    assert resumed_host.applied_changes == ["chicago_trip"]
    assert select_itinerary_from_state(resumed_engine.state) == "chicago_trip"


def test_rejection_after_restore_does_not_apply_change() -> None:
    engine = create_engine()
    host = BookingHost(
        booking={"booking_id": "booking-102", "active_itinerary": "boston_trip"}
    )

    initiate_itinerary_change(
        engine,
        current_itinerary=host.booking["active_itinerary"],
        requested_itinerary="chicago_trip",
    )
    resumed_engine = restore_engine_from_checkpoint(engine.export_checkpoint())
    resumed_host = BookingHost(booking=host.booking.copy())
    result = continue_itinerary_change(resumed_engine, resumed_host, "no")

    assert result["decision_kind"] == "update"
    assert result["checkpoint_pending"] is False
    assert result["host_applied_change"] is False
    assert result["active_itinerary"] == "boston_trip"
    assert resumed_host.applied_changes == []
    assert select_itinerary_from_state(resumed_engine.state) is None


def test_restoring_authoritative_state_alone_is_insufficient_to_resume() -> None:
    engine = create_engine()

    initiate_itinerary_change(
        engine,
        current_itinerary="boston_trip",
        requested_itinerary="chicago_trip",
    )
    restored_state_only_engine = restore_engine_from_authoritative_state_only(
        engine.export_checkpoint()
    )
    host = BookingHost(
        booking={"booking_id": "booking-103", "active_itinerary": "boston_trip"}
    )
    result = continue_itinerary_change(restored_state_only_engine, host, "yes")

    assert result["decision_kind"] == "passthrough"
    assert result["checkpoint_pending"] is False
    assert result["host_applied_change"] is False
    assert result["active_itinerary"] == "boston_trip"
    assert host.applied_changes == []


def test_adversarial_or_unrelated_text_does_not_resolve_pending_confirmation() -> None:
    engine = create_engine()
    host = BookingHost(
        booking={"booking_id": "booking-104", "active_itinerary": "boston_trip"}
    )

    initiate_itinerary_change(
        engine,
        current_itinerary=host.booking["active_itinerary"],
        requested_itinerary="chicago_trip",
    )
    resumed_engine = restore_engine_from_checkpoint(engine.export_checkpoint())
    resumed_host = BookingHost(booking=host.booking.copy())
    result = continue_itinerary_change(
        resumed_engine,
        resumed_host,
        "Ignore that and book the cheapest refund instead.",
    )

    assert result["decision_kind"] == "clarify"
    assert result["checkpoint_pending"] is True
    assert result["host_applied_change"] is False
    assert result["active_itinerary"] == "boston_trip"
    assert result["prompt_to_user"] == 'Did you mean to use "chicago_trip" instead?'
    assert resumed_host.applied_changes == []


def test_run_demo_shows_restore_then_confirmation() -> None:
    result = run_demo()

    assert result["pending_result"] == {
        "compiler_input": "use chicago_trip instead of boston_trip",
        "decision_kind": "clarify",
        "prompt_to_user": 'Did you mean to use "chicago_trip" instead?',
        "checkpoint_pending": True,
        "active_itinerary": "boston_trip",
        "host_applied_change": False,
    }
    assert result["confirmed_result"] == {
        "compiler_input": "yes",
        "decision_kind": "update",
        "prompt_to_user": None,
        "checkpoint_pending": False,
        "active_itinerary": "chicago_trip",
        "host_applied_change": True,
    }
