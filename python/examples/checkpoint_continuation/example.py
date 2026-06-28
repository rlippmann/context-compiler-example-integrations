"""Minimal checkpoint-continuation example for a travel booking change."""

from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from context_compiler import POLICY_USE, State, create_engine, get_policy_items
from context_compiler.engine import Checkpoint, Engine, State as EngineState


class BookingRecord(TypedDict):
    booking_id: str
    active_itinerary: str


class BookingChangeRuntimeResult(TypedDict):
    compiler_input: str
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    checkpoint_pending: bool
    active_itinerary: str
    host_applied_change: bool


@dataclass
class CheckpointStore:
    """Host-owned persistence for serialized engine checkpoints."""

    saved_checkpoint: Checkpoint | None = None

    def save(self, checkpoint: Checkpoint) -> None:
        self.saved_checkpoint = checkpoint

    def load(self) -> Checkpoint:
        if self.saved_checkpoint is None:
            raise ValueError("no checkpoint saved")
        return self.saved_checkpoint


@dataclass
class BookingHost:
    """Host-owned runtime behavior for the booking example."""

    booking: BookingRecord
    applied_changes: list[str] = field(default_factory=list)

    def apply_selected_itinerary(self, state: State) -> bool:
        selected_itinerary = select_itinerary_from_state(state)
        if selected_itinerary is None:
            return False

        self.booking["active_itinerary"] = selected_itinerary
        self.applied_changes.append(selected_itinerary)
        return True


def select_itinerary_from_state(state: State) -> str | None:
    """Select the host-visible itinerary from authoritative state."""

    use_items = list(get_policy_items(state, POLICY_USE))
    if not use_items:
        return None
    return use_items[0]


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


def initiate_itinerary_change(
    engine: Engine,
    *,
    current_itinerary: str,
    requested_itinerary: str,
) -> BookingChangeRuntimeResult:
    """Ask Context Compiler to hold a travel change behind confirmation."""

    compiler_input = f"use {requested_itinerary} instead of {current_itinerary}"
    decision = engine.step(compiler_input)

    return {
        "compiler_input": compiler_input,
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "checkpoint_pending": engine.has_pending_clarification(),
        "active_itinerary": select_itinerary_from_state(engine.state)
        or current_itinerary,
        "host_applied_change": False,
    }


def restore_engine_from_checkpoint(checkpoint: Checkpoint) -> Engine:
    """Restore both authoritative state and pending continuation state."""

    engine = create_engine()
    engine.import_checkpoint(checkpoint)
    return engine


def restore_engine_from_authoritative_state_only(
    checkpoint: Checkpoint,
) -> Engine:
    """Restore only authoritative state, without pending continuation state."""

    authoritative_state = cast(EngineState, checkpoint["authoritative_state"])
    return create_engine(state=authoritative_state)


def continue_itinerary_change(
    engine: Engine,
    host: BookingHost,
    user_input: str,
) -> BookingChangeRuntimeResult:
    """Resume a pending change and apply host behavior only after confirmation."""

    decision = engine.step(user_input)
    host_applied_change = False
    if _decision_kind_name(decision) == "update":
        host_applied_change = host.apply_selected_itinerary(engine.state)

    return {
        "compiler_input": user_input,
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "checkpoint_pending": engine.has_pending_clarification(),
        "active_itinerary": host.booking["active_itinerary"],
        "host_applied_change": host_applied_change,
    }


def run_demo() -> dict[str, BookingChangeRuntimeResult | Checkpoint]:
    """Run a deterministic checkpoint-continuation demonstration."""

    initial_booking: BookingRecord = {
        "booking_id": "booking-100",
        "active_itinerary": "boston_trip",
    }
    first_host = BookingHost(booking=initial_booking.copy())
    first_engine = create_engine()
    checkpoint_store = CheckpointStore()

    pending_result = initiate_itinerary_change(
        first_engine,
        current_itinerary=first_host.booking["active_itinerary"],
        requested_itinerary="chicago_trip",
    )
    checkpoint_store.save(first_engine.export_checkpoint())

    resumed_engine = restore_engine_from_checkpoint(checkpoint_store.load())
    resumed_host = BookingHost(booking=first_host.booking.copy())
    confirmed_result = continue_itinerary_change(resumed_engine, resumed_host, "yes")

    return {
        "pending_result": pending_result,
        "confirmed_result": confirmed_result,
        "saved_checkpoint": checkpoint_store.load(),
    }


if __name__ == "__main__":
    print(run_demo())
