from fastapi.testclient import TestClient

from context_compiler_example_integrations.examples.checkpoint_continuation.fastapi.app import (
    BookingStore,
    CheckpointStore,
    create_app,
    restore_engine_from_persisted_state,
)


def _create_client() -> tuple[TestClient, CheckpointStore, BookingStore]:
    checkpoint_store = CheckpointStore()
    booking_store = BookingStore()
    app = create_app(
        checkpoint_store=checkpoint_store,
        booking_store=booking_store,
    )
    return TestClient(app), checkpoint_store, booking_store


def test_change_trip_persists_authoritative_state_json() -> None:
    client, checkpoint_store, booking_store = _create_client()

    response = client.post("/change-trip", json={"booking_id": "booking-201"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_kind"] == "update"
    assert payload["message_to_user"] is None
    assert payload["selected_itinerary"] == "chicago_trip"
    assert '"chicago_trip":"use"' in payload["persisted_state_json"]
    assert checkpoint_store.has("booking-201") is True
    assert checkpoint_store.load("booking-201") == payload["persisted_state_json"]
    assert booking_store.get_or_create("booking-201") == {
        "booking_id": "booking-201",
        "active_itinerary": "boston_trip",
    }


def test_fresh_request_restores_state_and_applies_booking_change() -> None:
    client, checkpoint_store, booking_store = _create_client()

    client.post("/change-trip", json={"booking_id": "booking-202"})
    assert checkpoint_store.has("booking-202") is True

    response = client.post("/apply-trip", json={"booking_id": "booking-202"})

    assert response.status_code == 200
    assert response.json() == {
        "host_applied_change": True,
        "selected_itinerary": "chicago_trip",
        "booking": {
            "booking_id": "booking-202",
            "active_itinerary": "chicago_trip",
        },
    }
    assert booking_store.get_or_create("booking-202")["active_itinerary"] == (
        "chicago_trip"
    )


def test_restore_without_saved_itinerary_does_not_apply_change() -> None:
    client, checkpoint_store, booking_store = _create_client()

    checkpoint_store.save("booking-203", '{"policies":{},"premise":null,"version":2}')

    response = client.post("/apply-trip", json={"booking_id": "booking-203"})

    assert response.status_code == 200
    assert response.json() == {
        "host_applied_change": False,
        "selected_itinerary": None,
        "booking": {
            "booking_id": "booking-203",
            "active_itinerary": "boston_trip",
        },
    }
    assert booking_store.get_or_create("booking-203")["active_itinerary"] == (
        "boston_trip"
    )


def test_restore_engine_from_persisted_state_round_trips_authoritative_state() -> None:
    client, checkpoint_store, _ = _create_client()

    response = client.post("/change-trip", json={"booking_id": "booking-204"})
    state_json = response.json()["persisted_state_json"]
    restored_engine = restore_engine_from_persisted_state(state_json)

    assert restored_engine.export_json() == state_json
    assert checkpoint_store.load("booking-204") == state_json


def test_get_booking_returns_host_owned_booking_state() -> None:
    client, _, _ = _create_client()

    response = client.get("/booking", params={"booking_id": "booking-206"})

    assert response.status_code == 200
    assert response.json() == {
        "booking_id": "booking-206",
        "active_itinerary": "boston_trip",
    }
