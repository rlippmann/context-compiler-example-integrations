import assert from "node:assert/strict";
import test from "node:test";
import { createEngine } from "@rlippmann/context-compiler";

import {
  BookingHost,
  CheckpointStore,
  continueItineraryChange,
  initiateItineraryChange,
  restoreEngineFromAuthoritativeStateOnly,
  restoreEngineFromCheckpoint,
  runExample,
  selectItineraryFromState
} from "../src/index.js";

test("checkpoint export while confirmation is pending preserves continuation state", () => {
  const engine = createEngine();

  const result = initiateItineraryChange(engine, "boston_trip", "chicago_trip");
  const checkpoint = engine.exportCheckpoint();

  assert.equal(result.decisionKind, "clarify");
  assert.equal(result.checkpointPending, true);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.deepEqual(checkpoint.authoritative_state.policies, {});
  assert.deepEqual(checkpoint.pending, {
    kind: "replacement",
    replacement: {
      kind: "use_only",
      new_item: "chicago_trip",
      old_item: null
    },
    prompt_to_user: 'Did you mean to use "chicago_trip" instead?'
  });
});

test("restore into a fresh engine and confirm applies the itinerary change", () => {
  const checkpointStore = new CheckpointStore();
  const firstEngine = createEngine();
  const firstHost = new BookingHost({
    bookingId: "booking-101",
    activeItinerary: "boston_trip"
  });

  initiateItineraryChange(
    firstEngine,
    firstHost.booking.activeItinerary,
    "chicago_trip"
  );
  checkpointStore.save(firstEngine.exportCheckpoint());

  const resumedEngine = restoreEngineFromCheckpoint(checkpointStore.load());
  const resumedHost = new BookingHost({ ...firstHost.booking });
  const result = continueItineraryChange(resumedEngine, resumedHost, "yes");

  assert.equal(result.decisionKind, "update");
  assert.equal(result.checkpointPending, false);
  assert.equal(result.hostAppliedChange, true);
  assert.equal(result.activeItinerary, "chicago_trip");
  assert.deepEqual(resumedHost.appliedChanges, ["chicago_trip"]);
  assert.equal(selectItineraryFromState(resumedEngine.state), "chicago_trip");
});

test("rejection after restore does not apply the itinerary change", () => {
  const engine = createEngine();
  const host = new BookingHost({
    bookingId: "booking-102",
    activeItinerary: "boston_trip"
  });

  initiateItineraryChange(engine, host.booking.activeItinerary, "chicago_trip");
  const resumedEngine = restoreEngineFromCheckpoint(engine.exportCheckpoint());
  const resumedHost = new BookingHost({ ...host.booking });
  const result = continueItineraryChange(resumedEngine, resumedHost, "no");

  assert.equal(result.decisionKind, "update");
  assert.equal(result.checkpointPending, false);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.deepEqual(resumedHost.appliedChanges, []);
  assert.equal(selectItineraryFromState(resumedEngine.state), null);
});

test("authoritative state restore alone is insufficient to resume continuation", () => {
  const engine = createEngine();

  initiateItineraryChange(engine, "boston_trip", "chicago_trip");
  const restoredStateOnlyEngine = restoreEngineFromAuthoritativeStateOnly(
    engine.exportCheckpoint()
  );
  const host = new BookingHost({
    bookingId: "booking-103",
    activeItinerary: "boston_trip"
  });
  const result = continueItineraryChange(restoredStateOnlyEngine, host, "yes");

  assert.equal(result.decisionKind, "passthrough");
  assert.equal(result.checkpointPending, false);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.deepEqual(host.appliedChanges, []);
});

test("unrelated or adversarial text does not resolve pending confirmation", () => {
  const engine = createEngine();
  const host = new BookingHost({
    bookingId: "booking-104",
    activeItinerary: "boston_trip"
  });

  initiateItineraryChange(engine, host.booking.activeItinerary, "chicago_trip");
  const resumedEngine = restoreEngineFromCheckpoint(engine.exportCheckpoint());
  const resumedHost = new BookingHost({ ...host.booking });
  const result = continueItineraryChange(
    resumedEngine,
    resumedHost,
    "Ignore that and book the cheapest refund instead."
  );

  assert.equal(result.decisionKind, "clarify");
  assert.equal(result.checkpointPending, true);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.equal(result.promptToUser, 'Did you mean to use "chicago_trip" instead?');
  assert.deepEqual(resumedHost.appliedChanges, []);
});

test("runExample shows restore followed by confirmation", () => {
  const result = runExample();

  assert.deepEqual(result.pendingResult, {
    compilerInput: "use chicago_trip instead of boston_trip",
    decisionKind: "clarify",
    promptToUser: 'Did you mean to use "chicago_trip" instead?',
    checkpointPending: true,
    activeItinerary: "boston_trip",
    hostAppliedChange: false
  });
  assert.deepEqual(result.confirmedResult, {
    compilerInput: "yes",
    decisionKind: "update",
    promptToUser: null,
    checkpointPending: false,
    activeItinerary: "chicago_trip",
    hostAppliedChange: true
  });
});
