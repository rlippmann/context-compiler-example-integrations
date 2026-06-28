"""Small FastAPI checkpoint-continuation example for travel booking."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from context_compiler import POLICY_USE, State, create_engine, get_policy_items
from context_compiler.engine import Checkpoint, Engine
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
    decision_kind: Literal["clarify"]
    prompt_to_user: str | None
    checkpoint_pending: bool
    booking: BookingResponse


class ConfirmResponse(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    checkpoint_pending: bool
    host_applied_change: bool
    booking: BookingResponse


class ChangeTripRequest(BaseModel):
    booking_id: str


class ConfirmRequest(BaseModel):
    booking_id: str
    user_input: str


@dataclass
class CheckpointStore:
    """Host-owned checkpoint persistence for stateless HTTP requests."""

    checkpoints_by_booking_id: dict[str, Checkpoint] = field(default_factory=dict)

    def save(self, booking_id: str, checkpoint: Checkpoint) -> None:
        self.checkpoints_by_booking_id[booking_id] = checkpoint

    def load(self, booking_id: str) -> Checkpoint:
        checkpoint = self.checkpoints_by_booking_id.get(booking_id)
        if checkpoint is None:
            raise KeyError(booking_id)
        return checkpoint

    def has(self, booking_id: str) -> bool:
        return booking_id in self.checkpoints_by_booking_id


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

    def apply_selected_itinerary(self, booking_id: str, state: State) -> bool:
        selected_itinerary = select_itinerary_from_state(state)
        if selected_itinerary is None:
            return False

        booking = self.booking_store.get_or_create(booking_id)
        booking["active_itinerary"] = selected_itinerary
        self.applied_changes.append(selected_itinerary)
        return True


def select_itinerary_from_state(state: State) -> str | None:
    use_items = list(get_policy_items(state, POLICY_USE))
    if not use_items:
        return None
    return use_items[0]


def restore_engine_from_checkpoint(checkpoint: Checkpoint) -> Engine:
    engine = create_engine()
    engine.import_checkpoint(checkpoint)
    return engine


def restore_engine_from_authoritative_state_only(checkpoint: Checkpoint) -> Engine:
    authoritative_state = checkpoint["authoritative_state"]
    return create_engine(state=authoritative_state)


def _fresh_engine() -> Engine:
    """Create a fresh engine per request to demonstrate stateless boundaries."""

    return create_engine()


def create_app(
    *,
    checkpoint_store: CheckpointStore | None = None,
    booking_store: BookingStore | None = None,
    engine_factory: Callable[[], Engine] = _fresh_engine,
) -> FastAPI:
    checkpoint_store = checkpoint_store or CheckpointStore()
    booking_store = booking_store or BookingStore()
    booking_host = BookingHost(booking_store=booking_store)

    app = FastAPI(title="checkpoint-continuation-fastapi-example")
    app.state.checkpoint_store = checkpoint_store
    app.state.booking_store = booking_store
    app.state.booking_host = booking_host
    app.state.engine_factory = engine_factory

    @app.post("/change-trip")
    def change_trip(request: ChangeTripRequest) -> ChangeTripResponse:
        booking = booking_store.get_or_create(request.booking_id)
        engine = engine_factory()

        compiler_input = f"use chicago_trip instead of {booking['active_itinerary']}"
        decision = engine.step(compiler_input)
        checkpoint_store.save(request.booking_id, engine.export_checkpoint())

        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "checkpoint_pending": engine.has_pending_clarification(),
            "booking": {
                "booking_id": booking["booking_id"],
                "active_itinerary": booking["active_itinerary"],
            },
        }

    @app.post("/confirm")
    def confirm(request: ConfirmRequest) -> ConfirmResponse:
        booking = booking_store.get_or_create(request.booking_id)
        try:
            checkpoint = checkpoint_store.load(request.booking_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="checkpoint not found") from exc

        engine = restore_engine_from_checkpoint(checkpoint)
        decision = engine.step(request.user_input)
        checkpoint_store.save(request.booking_id, engine.export_checkpoint())

        host_applied_change = False
        if decision["kind"].value == "update":
            host_applied_change = booking_host.apply_selected_itinerary(
                request.booking_id, engine.state
            )

        return {
            "decision_kind": decision["kind"].value,
            "prompt_to_user": decision.get("prompt_to_user"),
            "checkpoint_pending": engine.has_pending_clarification(),
            "host_applied_change": host_applied_change,
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
