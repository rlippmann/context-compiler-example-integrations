"""Small FastAPI persistence example for travel booking."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from context_compiler import POLICY_USE, DecisionKind, PolicyValue, create_engine
from context_compiler.engine import Engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing_extensions import TypedDict


class BookingRecord(TypedDict):
    booking_id: str
    active_itinerary: str


class BookingResponse(TypedDict):
    booking_id: str
    active_itinerary: str


class ChangeTripResponse(TypedDict):
    decision_kind: Literal["error", "update", "passthrough"]
    message_to_user: str | None
    persisted_state_json: str
    selected_itinerary: str | None
    booking: BookingResponse


class ApplyTripResponse(TypedDict):
    host_applied_change: bool
    selected_itinerary: str | None
    booking: BookingResponse


class ChangeTripRequest(BaseModel):
    booking_id: str


@dataclass
class EnginePersistenceStore:
    """Host-owned authoritative state persistence for stateless HTTP requests."""

    states_by_booking_id: dict[str, str] = field(default_factory=dict)

    def save(self, booking_id: str, state_json: str) -> None:
        self.states_by_booking_id[booking_id] = state_json

    def load(self, booking_id: str) -> str:
        state_json = self.states_by_booking_id.get(booking_id)
        if state_json is None:
            raise KeyError(booking_id)
        return state_json

    def has(self, booking_id: str) -> bool:
        return booking_id in self.states_by_booking_id


@dataclass
class BookingStore:
    """Host-owned booking persistence for the example."""

    bookings_by_id: dict[str, BookingRecord] = field(default_factory=dict)

    def get_or_create(self, booking_id: str) -> BookingRecord:
        booking = self.bookings_by_id.get(booking_id)
        if booking is None:
            booking = {"booking_id": booking_id, "active_itinerary": "boston_trip"}
            self.bookings_by_id[booking_id] = booking
        return booking


@dataclass
class BookingHost:
    """Host-owned booking mutation logic."""

    booking_store: BookingStore
    applied_changes: list[str] = field(default_factory=list)

    def apply_selected_itinerary(
        self, booking_id: str, policies: Mapping[str, PolicyValue]
    ) -> bool:
        selected_itinerary = select_itinerary_from_policies(policies)
        if selected_itinerary is None:
            return False

        booking = self.booking_store.get_or_create(booking_id)
        booking["active_itinerary"] = selected_itinerary
        self.applied_changes.append(selected_itinerary)
        return True


def select_itinerary_from_policies(policies: Mapping[str, PolicyValue]) -> str | None:
    for item, kind in policies.items():
        if kind == POLICY_USE:
            return item
    return None


def restore_engine_from_persisted_state(state_json: str) -> Engine:
    engine = create_engine()
    engine.import_json(state_json)
    return engine


def _fresh_engine() -> Engine:
    return create_engine()


def create_app(
    *,
    engine_persistence_store: EnginePersistenceStore | None = None,
    booking_store: BookingStore | None = None,
    engine_factory: Callable[[], Engine] = _fresh_engine,
) -> FastAPI:
    engine_persistence_store = engine_persistence_store or EnginePersistenceStore()
    booking_store = booking_store or BookingStore()
    booking_host = BookingHost(booking_store=booking_store)

    app = FastAPI(title="state-persistence-fastapi-example")
    app.state.engine_persistence_store = engine_persistence_store
    app.state.booking_store = booking_store
    app.state.booking_host = booking_host
    app.state.engine_factory = engine_factory

    @app.post("/change-trip")
    def change_trip(request: ChangeTripRequest) -> ChangeTripResponse:
        booking = booking_store.get_or_create(request.booking_id)
        engine = engine_factory()

        compiler_input = "use chicago_trip"
        decision = engine.step(compiler_input)
        state_json = engine.export_json()
        engine_persistence_store.save(request.booking_id, state_json)

        selected_itinerary = select_itinerary_from_policies(engine.policies)
        decision_kind: Literal["error", "update", "passthrough"]
        if decision["kind"] == DecisionKind.ERROR:
            decision_kind = "error"
        elif decision["kind"] == DecisionKind.UPDATE:
            decision_kind = "update"
        else:
            decision_kind = "passthrough"

        return {
            "decision_kind": decision_kind,
            "message_to_user": decision["message"],
            "persisted_state_json": state_json,
            "selected_itinerary": selected_itinerary,
            "booking": {
                "booking_id": booking["booking_id"],
                "active_itinerary": booking["active_itinerary"],
            },
        }

    @app.post("/apply-trip")
    def apply_trip(request: ChangeTripRequest) -> ApplyTripResponse:
        booking = booking_store.get_or_create(request.booking_id)
        try:
            state_json = engine_persistence_store.load(request.booking_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="saved state not found"
            ) from exc

        engine = restore_engine_from_persisted_state(state_json)
        host_applied_change = booking_host.apply_selected_itinerary(
            request.booking_id, engine.policies
        )

        return {
            "host_applied_change": host_applied_change,
            "selected_itinerary": select_itinerary_from_policies(engine.policies),
            "booking": {
                "booking_id": booking["booking_id"],
                "active_itinerary": booking["active_itinerary"],
            },
        }

    @app.get("/booking")
    def get_booking(booking_id: str) -> BookingResponse:
        booking = booking_store.get_or_create(booking_id)
        return {
            "booking_id": booking["booking_id"],
            "active_itinerary": booking["active_itinerary"],
        }

    return app


app = create_app()


if __name__ == "__main__":
    print(
        "Run with: uv run fastapi dev "
        "python/examples/checkpoint_continuation/fastapi/app.py"
    )
