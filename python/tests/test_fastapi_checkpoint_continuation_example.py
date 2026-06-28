from fastapi.testclient import TestClient

from python.examples.checkpoint_continuation.fastapi.app import (
    BookingStore,
    CheckpointStore,
    create_app,
    restore_engine_from_authoritative_state_only,
)


def _create_client() -> tuple[TestClient, CheckpointStore, BookingStore]:
    checkpoint_store = CheckpointStore()
    booking_store = BookingStore()
    app = create_app(
        checkpoint_store=checkpoint_store,
        booking_store=booking_store,
    )
    return TestClient(app), checkpoint_store, booking_store


def test_initial_request_enters_pending_state_and_persists_checkpoint() -> None:
    client, checkpoint_store, booking_store = _create_client()

    response = client.post("/change-trip", json={"booking_id": "booking-201"})

    assert response.status_code == 200
    assert response.json() == {
        "decision_kind": "clarify",
        "prompt_to_user": 'Did you mean to use "chicago_trip" instead?',
        "checkpoint_pending": True,
        "booking": {
            "booking_id": "booking-201",
            "active_itinerary": "boston_trip",
        },
    }
    assert checkpoint_store.has("booking-201") is True
    assert booking_store.get_or_create("booking-201") == {
        "booking_id": "booking-201",
        "active_itinerary": "boston_trip",
    }
    assert checkpoint_store.load("booking-201")["pending"] == {
        "kind": "replacement",
        "replacement": {
            "kind": "use_only",
            "new_item": "chicago_trip",
            "old_item": None,
        },
        "prompt_to_user": 'Did you mean to use "chicago_trip" instead?',
    }


def test_fresh_request_restores_checkpoint_and_confirmation_applies_change() -> None:
    client, checkpoint_store, booking_store = _create_client()

    client.post("/change-trip", json={"booking_id": "booking-202"})
    assert checkpoint_store.has("booking-202") is True

    response = client.post(
        "/confirm",
        json={"booking_id": "booking-202", "user_input": "yes"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision_kind": "update",
        "prompt_to_user": None,
        "checkpoint_pending": False,
        "host_applied_change": True,
        "booking": {
            "booking_id": "booking-202",
            "active_itinerary": "chicago_trip",
        },
    }
    assert booking_store.get_or_create("booking-202")["active_itinerary"] == (
        "chicago_trip"
    )
    assert checkpoint_store.load("booking-202")["pending"] is None


def test_rejection_does_not_apply_booking_change() -> None:
    client, checkpoint_store, booking_store = _create_client()

    client.post("/change-trip", json={"booking_id": "booking-203"})

    response = client.post(
        "/confirm",
        json={"booking_id": "booking-203", "user_input": "no"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision_kind": "update",
        "prompt_to_user": None,
        "checkpoint_pending": False,
        "host_applied_change": False,
        "booking": {
            "booking_id": "booking-203",
            "active_itinerary": "boston_trip",
        },
    }
    assert booking_store.get_or_create("booking-203")["active_itinerary"] == (
        "boston_trip"
    )
    assert checkpoint_store.load("booking-203")["pending"] is None


def test_unrelated_text_does_not_resolve_pending_confirmation() -> None:
    client, checkpoint_store, booking_store = _create_client()

    client.post("/change-trip", json={"booking_id": "booking-204"})

    response = client.post(
        "/confirm",
        json={
            "booking_id": "booking-204",
            "user_input": "Ignore that and book the cheapest refund instead.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision_kind": "clarify",
        "prompt_to_user": 'Did you mean to use "chicago_trip" instead?',
        "checkpoint_pending": True,
        "host_applied_change": False,
        "booking": {
            "booking_id": "booking-204",
            "active_itinerary": "boston_trip",
        },
    }
    assert booking_store.get_or_create("booking-204")["active_itinerary"] == (
        "boston_trip"
    )
    assert checkpoint_store.load("booking-204")["pending"] is not None


def test_authoritative_state_only_restore_is_insufficient() -> None:
    client, checkpoint_store, booking_store = _create_client()

    client.post("/change-trip", json={"booking_id": "booking-205"})
    state_only_engine = restore_engine_from_authoritative_state_only(
        checkpoint_store.load("booking-205")
    )
    decision = state_only_engine.step("yes")

    assert decision["kind"].value == "passthrough"
    assert state_only_engine.has_pending_clarification() is False
    assert booking_store.get_or_create("booking-205")["active_itinerary"] == (
        "boston_trip"
    )


def test_get_booking_returns_host_owned_booking_state() -> None:
    client, _, _ = _create_client()

    response = client.get("/booking", params={"booking_id": "booking-206"})

    assert response.status_code == 200
    assert response.json() == {
        "booking_id": "booking-206",
        "active_itinerary": "boston_trip",
    }
