import assert from "node:assert/strict";
import test from "node:test";
import { Engine } from "@rlippmann/context-compiler";

import {
  BookingHost,
  EnginePersistenceStore,
  applyRestoredItinerary,
  persistItinerarySelection,
  restoreEngineFromPersistedState,
  runExample,
  selectItineraryFromState
} from "../src/index.js";
import { snapshotState } from "../src/compiler-state.js";

test("use chicago_trip produces authoritative use state", () => {
  const engine = new Engine();

  const result = persistItinerarySelection(engine, "chicago_trip");

  assert.equal(result.decisionKind, "update");
  assert.equal(result.messageToUser, null);
  assert.equal(result.selectedItinerary, "chicago_trip");
  assert.equal(result.hostAppliedChange, false);
  assert.deepEqual(snapshotState(engine), {
    premise: null,
    policies: { chicago_trip: "use" },
    version: 2
  });
});

test("exported JSON contains the authoritative itinerary state", () => {
  const engine = new Engine();

  const result = persistItinerarySelection(engine, "chicago_trip");

  assert.deepEqual(JSON.parse(result.persistedStateJson), {
    premise: null,
    policies: { chicago_trip: "use" },
    version: 2
  });
});

test("a fresh engine restores chicago_trip from persisted state", () => {
  const firstEngine = new Engine();
  const persisted = persistItinerarySelection(firstEngine, "chicago_trip");

  const restoredEngine = restoreEngineFromPersistedState(persisted.persistedStateJson);

  assert.equal(selectItineraryFromState(snapshotState(restoredEngine)), "chicago_trip");
  assert.deepEqual(snapshotState(restoredEngine), snapshotState(firstEngine));
});

test("the host applies the booking change from restored authoritative state", () => {
  const firstEngine = new Engine();
  const persisted = persistItinerarySelection(firstEngine, "chicago_trip");
  const restoredEngine = restoreEngineFromPersistedState(persisted.persistedStateJson);
  const host = new BookingHost({
    bookingId: "booking-100",
    activeItinerary: "boston_trip"
  });

  const result = applyRestoredItinerary(restoredEngine, host);

  assert.equal(result.decisionKind, "update");
  assert.equal(result.selectedItinerary, "chicago_trip");
  assert.equal(result.hostAppliedChange, true);
  assert.equal(result.activeItinerary, "chicago_trip");
  assert.equal(host.booking.activeItinerary, "chicago_trip");
  assert.deepEqual(host.appliedChanges, ["chicago_trip"]);
});

test("persistence storage is host-owned and no continuation state is required", () => {
  const firstEngine = new Engine();
  const persisted = persistItinerarySelection(firstEngine, "chicago_trip");
  const store = new EnginePersistenceStore();
  store.save(persisted.persistedStateJson);

  const restoredEngine = restoreEngineFromPersistedState(store.load());

  assert.equal(restoredEngine.step("yes").kind, "no_directive");
  assert.equal(selectItineraryFromState(snapshotState(restoredEngine)), "chicago_trip");
});

test("runExample demonstrates persistence followed by an observable host update", () => {
  const result = runExample();

  assert.equal(result.persistedResult.compilerInput, "use chicago_trip");
  assert.equal(result.persistedResult.decisionKind, "update");
  assert.equal(result.persistedResult.selectedItinerary, "chicago_trip");
  assert.equal(result.persistedResult.hostAppliedChange, false);
  assert.equal(result.appliedResult.compilerInput, "");
  assert.equal(result.appliedResult.decisionKind, "update");
  assert.equal(result.appliedResult.selectedItinerary, "chicago_trip");
  assert.equal(result.appliedResult.hostAppliedChange, true);
  assert.equal(result.appliedResult.activeItinerary, "chicago_trip");
  assert.deepEqual(JSON.parse(result.savedStateJson), {
    premise: null,
    policies: { chicago_trip: "use" },
    version: 2
  });
});
