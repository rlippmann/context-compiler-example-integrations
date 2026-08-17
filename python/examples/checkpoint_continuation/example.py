"""Minimal persistence example for a travel booking change."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from context_compiler import Decision, DecisionKind, Engine, POLICY_USE, PolicyValue


class BookingRecord(TypedDict):
    booking_id: str
    active_itinerary: str


class BookingChangeRuntimeResult(TypedDict):
    compiler_input: str
    decision_kind: Literal["error", "update", "passthrough"]
    message_to_user: str | None
    persisted_state_json: str
    selected_itinerary: str | None
    host_applied_change: bool
    active_itinerary: str


@dataclass
class EnginePersistenceStore:
    """Host-owned persistence for serialized authoritative compiler state."""

    saved_state_json: str | None = None

    def save(self, state_json: str) -> None:
        self.saved_state_json = state_json

    def load(self) -> str:
        if self.saved_state_json is None:
            raise ValueError("no saved state")
        return self.saved_state_json


@dataclass
class BookingHost:
    """Host-owned runtime behavior for the booking example."""

    booking: BookingRecord
    applied_changes: list[str] = field(default_factory=list)

    def apply_selected_itinerary(self, policies: Mapping[str, PolicyValue]) -> bool:
        selected_itinerary = select_itinerary_from_policies(policies)
        if selected_itinerary is None:
            return False

        self.booking["active_itinerary"] = selected_itinerary
        self.applied_changes.append(selected_itinerary)
        return True


def select_itinerary_from_policies(policies: Mapping[str, PolicyValue]) -> str | None:
    """Select the host-visible itinerary from authoritative state."""

    for item, kind in policies.items():
        if kind == POLICY_USE:
            return item
    return None


def _decision_kind_name(
    decision: Decision,
) -> Literal["error", "update", "passthrough"]:
    kind = decision.kind
    if kind == DecisionKind.ERROR:
        return "error"
    if kind == DecisionKind.UPDATE:
        return "update"
    if kind == DecisionKind.NO_DIRECTIVE:
        return "passthrough"
    raise ValueError(f"unexpected decision kind: {kind}")


def persist_itinerary_selection(
    engine: Engine,
    *,
    requested_itinerary: str,
) -> BookingChangeRuntimeResult:
    """Persist authoritative state after selecting an itinerary."""

    compiler_input = f"use {requested_itinerary}"
    decision = engine.step(compiler_input)
    persisted_state_json = engine.export_json()
    selected_itinerary = select_itinerary_from_policies(engine.policies)

    return {
        "compiler_input": compiler_input,
        "decision_kind": _decision_kind_name(decision),
        "message_to_user": decision.message
        if decision.kind == DecisionKind.ERROR
        else None,
        "persisted_state_json": persisted_state_json,
        "selected_itinerary": selected_itinerary,
        "host_applied_change": False,
        "active_itinerary": requested_itinerary
        if selected_itinerary is not None
        else "boston_trip",
    }


def restore_engine_from_persisted_state(state_json: str) -> Engine:
    """Restore authoritative compiler state into a fresh engine."""

    engine = Engine()
    engine.import_json(state_json)
    return engine


def apply_restored_itinerary(
    engine: Engine, host: BookingHost
) -> BookingChangeRuntimeResult:
    """Apply host behavior from restored authoritative compiler state."""

    host_applied_change = host.apply_selected_itinerary(engine.policies)
    selected_itinerary = select_itinerary_from_policies(engine.policies)

    return {
        "compiler_input": "",
        "decision_kind": "update" if host_applied_change else "passthrough",
        "message_to_user": None,
        "persisted_state_json": engine.export_json(),
        "selected_itinerary": selected_itinerary,
        "host_applied_change": host_applied_change,
        "active_itinerary": host.booking["active_itinerary"],
    }


def run_demo() -> dict[str, BookingChangeRuntimeResult | str]:
    """Run a deterministic persistence demonstration."""

    initial_booking: BookingRecord = {
        "booking_id": "booking-100",
        "active_itinerary": "boston_trip",
    }
    first_engine = Engine()
    engine_persistence_store = EnginePersistenceStore()

    persisted_result = persist_itinerary_selection(
        first_engine,
        requested_itinerary="chicago_trip",
    )
    engine_persistence_store.save(persisted_result["persisted_state_json"])

    restored_engine = restore_engine_from_persisted_state(
        engine_persistence_store.load()
    )
    restored_host = BookingHost(booking=initial_booking.copy())
    applied_result = apply_restored_itinerary(restored_engine, restored_host)

    return {
        "persisted_result": persisted_result,
        "applied_result": applied_result,
        "saved_state_json": engine_persistence_store.load(),
    }


if __name__ == "__main__":
    print(run_demo())
