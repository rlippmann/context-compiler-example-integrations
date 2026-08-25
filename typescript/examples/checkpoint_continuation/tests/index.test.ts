import assert from "node:assert/strict";
import test from "node:test";
import { Engine } from "@rlippmann/context-compiler";

import {
  CheckpointStore,
  initiateItineraryChange,
  restoreEngineFromAuthoritativeStateOnly,
  restoreEngineFromCheckpoint,
  runExample,
  selectItineraryFromState
} from "../src/index.js";
import { snapshotState } from "../src/compiler-state.js";

test("a conflicting replacement returns a semantic error and exports unchanged state", () => {
  const engine = new Engine();
  const result = initiateItineraryChange(engine, "boston_trip", "chicago_trip");
  const checkpoint = engine.export_json();

  assert.equal(result.decisionKind, "error");
  assert.equal(result.hostAppliedChange, false);
  assert.equal(result.activeItinerary, "boston_trip");
  assert.equal(
    result.promptToUser,
    '"boston_trip" is not currently in use.\nReplacement requires an active \'use\' policy.'
  );
  assert.deepEqual(JSON.parse(checkpoint), { premise: null, policies: {}, version: 2 });
});

test("restore into a fresh engine preserves authoritative policy state", () => {
  const store = new CheckpointStore();
  const firstEngine = new Engine();
  firstEngine.step("use boston_trip");
  store.save(firstEngine.export_json());

  const restoredEngine = restoreEngineFromCheckpoint(store.load());

  assert.equal(selectItineraryFromState(snapshotState(restoredEngine)), "boston_trip");
  assert.deepEqual(snapshotState(restoredEngine), snapshotState(firstEngine));
});

test("authoritative state restore does not create continuation state", () => {
  const engine = new Engine();
  engine.step("use boston_trip");

  const restoredEngine = restoreEngineFromAuthoritativeStateOnly(engine.export_json());

  assert.deepEqual(snapshotState(restoredEngine), snapshotState(engine));
});

test("runExample records the semantic error and restored state", () => {
  const result = runExample();

  assert.equal(result.initialResult.decisionKind, "error");
  assert.equal(result.initialResult.hostAppliedChange, false);
  assert.deepEqual(result.restoredState, { premise: null, policies: {}, version: 2 });
  assert.deepEqual(JSON.parse(result.savedCheckpoint), { premise: null, policies: {}, version: 2 });
});
