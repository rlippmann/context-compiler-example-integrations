import assert from "node:assert/strict";
import test from "node:test";
import { Engine } from "@rlippmann/context-compiler";

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
import { snapshotState } from "../src/compiler-state.js";

test("a conflicting replacement returns a 0.9 semantic error and exports unchanged state", () => {
  const engine = new Engine();
  const result = initiateItineraryChange(engine, "boston_trip", "chicago_trip");
  const checkpoint = engine.export_json();
  assert.equal(result.decisionKind, "error");
  assert.equal(result.checkpointPending, false);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.equal(result.promptToUser, '"boston_trip" is not currently in use.\nReplacement requires an active \'use\' policy.');
  assert.deepEqual(JSON.parse(checkpoint), { premise: null, policies: {}, version: 2 });
});

test("restore into a fresh engine preserves the authoritative state", () => {
  const store = new CheckpointStore();
  const firstEngine = new Engine();
  firstEngine.step("use boston_trip");
  store.save(firstEngine.export_json());
  const resumedEngine = restoreEngineFromCheckpoint(store.load());
  assert.equal(selectItineraryFromState(snapshotState(resumedEngine)), "boston_trip");
});

test("a confirmation input is ordinary non-directive text without pending compiler state", () => {
  const engine = new Engine();
  engine.step("use boston_trip");
  const host = new BookingHost({ bookingId: "booking-102", activeItinerary: "boston_trip" });
  const result = continueItineraryChange(engine, host, "yes");
  assert.equal(result.decisionKind, "no_directive");
  assert.equal(result.checkpointPending, false);
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.deepEqual(host.appliedChanges, []);
});

test("authoritative state restore is sufficient because 0.9 has no pending continuation state", () => {
  const engine = new Engine();
  engine.step("use boston_trip");
  const restored = restoreEngineFromAuthoritativeStateOnly(engine.export_json());
  assert.deepEqual(snapshotState(restored), snapshotState(engine));
});

test("runExample records the semantic error and unchanged restored state", () => {
  const result = runExample();
  assert.equal(result.pendingResult.decisionKind, "error");
  assert.equal(result.pendingResult.checkpointPending, false);
  assert.equal(result.pendingResult.hostAppliedChange, false);
  assert.equal(result.confirmedResult.decisionKind, "no_directive");
  assert.equal(result.confirmedResult.checkpointPending, false);
  assert.equal(result.confirmedResult.hostAppliedChange, false);
  assert.equal(result.confirmedResult.activeItinerary, "boston_trip");
  assert.deepEqual(JSON.parse(result.savedCheckpoint), { premise: null, policies: {}, version: 2 });
});
