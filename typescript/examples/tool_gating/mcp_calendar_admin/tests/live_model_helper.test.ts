import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createEngine } from "@rlippmann/context-compiler";

import {
  runLiveModelTurn,
  type SelectedToolCall
} from "../src/live_model.js";

const USER_INTENT =
  "Create an admin calendar event named Quarterly access review on calendar ops-admin.";

function readJsonl(path: string): string[] {
  try {
    return readFileSync(path, "utf8")
      .split("\n")
      .filter((line) => line.trim().length > 0);
  } catch {
    return [];
  }
}

function tempArtifactPath(): string {
  return join(mkdtempSync(join(tmpdir(), "mcp-calendar-admin-live-")), "tool_calls.jsonl");
}

test("absent state keeps protected tool hidden from model-visible surface", async () => {
  const artifactPath = tempArtifactPath();

  const result = await runLiveModelTurn({
    userIntent: USER_INTENT,
    artifactPath,
    modelToolSelector: async (): Promise<SelectedToolCall> => ({
      name: "calendar_view_events",
      arguments: { calendar_id: "ops-admin" }
    })
  });

  assert.equal(result.protectedToolExposed, false);
  assert.equal(result.selectedToolName, "calendar_view_events");
  assert.equal(result.executed, false);
  assert.equal(result.blockedReason, "protected admin tool was not exposed");
  assert.deepEqual(readJsonl(artifactPath), []);
});

test("authorized state exposes protected tool and records side effect", async () => {
  const artifactPath = tempArtifactPath();
  const engine = createEngine();
  engine.step("use calendar_admin");

  const result = await runLiveModelTurn({
    userIntent: USER_INTENT,
    authoritativeState: engine.state,
    artifactPath,
    modelToolSelector: async (): Promise<SelectedToolCall> => ({
      name: "calendar_admin_create_event",
      arguments: {
        calendar_id: "ops-admin",
        event_title: "Quarterly access review"
      }
    })
  });

  assert.equal(result.protectedToolExposed, true);
  assert.equal(result.selectedToolName, "calendar_admin_create_event");
  assert.equal(result.executed, true);
  assert.equal(
    result.toolResult,
    "created event 'Quarterly access review' on calendar 'ops-admin'"
  );
  assert.equal(result.sideEffectCount, 1);
  assert.equal(readJsonl(artifactPath).length, 1);
});

test("contradiction blocks before model tool selection", async () => {
  const artifactPath = tempArtifactPath();
  const engine = createEngine();
  engine.step("use calendar_admin");
  let modelCalled = false;

  const result = await runLiveModelTurn({
    userIntent: USER_INTENT,
    authoritativeState: engine.state,
    compilerInput: "prohibit calendar_admin",
    artifactPath,
    modelToolSelector: async (): Promise<SelectedToolCall> => {
      modelCalled = true;
      return {
        name: "calendar_admin_create_event",
        arguments: {
          calendar_id: "ops-admin",
          event_title: "Quarterly access review"
        }
      };
    }
  });

  assert.equal(result.decisionKind, "clarify");
  assert.equal(result.executed, false);
  assert.equal(modelCalled, false);
  assert.deepEqual(readJsonl(artifactPath), []);
});
