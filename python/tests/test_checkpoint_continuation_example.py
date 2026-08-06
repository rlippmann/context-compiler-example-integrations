from context_compiler import create_engine

from context_compiler_example_integrations.examples.checkpoint_continuation.example import (
    BookingHost,
    EnginePersistenceStore,
    apply_restored_itinerary,
    persist_itinerary_selection,
    restore_engine_from_persisted_state,
    run_demo,
    select_itinerary_from_policies,
)


def test_persisted_state_json_captures_authoritative_policy_state() -> None:
    engine = create_engine()

    result = persist_itinerary_selection(engine, requested_itinerary="chicago_trip")

    assert result["decision_kind"] == "update"
    assert result["message_to_user"] is None
    assert result["host_applied_change"] is False
    assert result["selected_itinerary"] == "chicago_trip"
    assert result["persisted_state_json"] == engine.export_json()
    assert '"chicago_trip":"use"' in result["persisted_state_json"]


def test_restore_into_fresh_engine_and_apply_selected_itinerary() -> None:
    engine_persistence_store = EnginePersistenceStore()
    first_engine = create_engine()
    first_host = BookingHost(
        booking={"booking_id": "booking-101", "active_itinerary": "boston_trip"}
    )

    persisted = persist_itinerary_selection(
        first_engine,
        requested_itinerary="chicago_trip",
    )
    engine_persistence_store.save(persisted["persisted_state_json"])

    restored_engine = restore_engine_from_persisted_state(
        engine_persistence_store.load()
    )
    restored_host = BookingHost(booking=first_host.booking.copy())
    result = apply_restored_itinerary(restored_engine, restored_host)

    assert result["decision_kind"] == "update"
    assert result["host_applied_change"] is True
    assert result["active_itinerary"] == "chicago_trip"
    assert restored_host.applied_changes == ["chicago_trip"]
    assert select_itinerary_from_policies(restored_engine.policies) == "chicago_trip"


def test_restore_without_selected_itinerary_does_not_apply_change() -> None:
    engine = create_engine()
    host = BookingHost(
        booking={"booking_id": "booking-102", "active_itinerary": "boston_trip"}
    )

    restored_engine = restore_engine_from_persisted_state(engine.export_json())
    result = apply_restored_itinerary(restored_engine, host)

    assert result["decision_kind"] == "passthrough"
    assert result["host_applied_change"] is False
    assert result["active_itinerary"] == "boston_trip"
    assert host.applied_changes == []


def test_run_demo_shows_persist_then_apply() -> None:
    result = run_demo()

    assert result["persisted_result"] == {
        "compiler_input": "use chicago_trip",
        "decision_kind": "update",
        "message_to_user": None,
        "persisted_state_json": result["saved_state_json"],
        "selected_itinerary": "chicago_trip",
        "host_applied_change": False,
        "active_itinerary": "chicago_trip",
    }
    assert result["applied_result"] == {
        "compiler_input": "",
        "decision_kind": "update",
        "message_to_user": None,
        "persisted_state_json": result["saved_state_json"],
        "selected_itinerary": "chicago_trip",
        "host_applied_change": True,
        "active_itinerary": "chicago_trip",
    }
