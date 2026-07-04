import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createEngine } from "@rlippmann/context-compiler";

import { runLiveModelTurn } from "../src/live_model.js";

const RUN_LIVE_MODEL_ENV_VAR = "RUN_MCP_CALENDAR_ADMIN_LIVE_MODEL";
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

test(
  "live model tool surface changes with authoritative state",
  { skip: process.env[RUN_LIVE_MODEL_ENV_VAR] !== "1" },
  async () => {
    const artifactPath = tempArtifactPath();

    const absentResult = await runLiveModelTurn({
      userIntent: USER_INTENT,
      artifactPath
    });

    assert.equal(absentResult.protectedToolExposed, false);
    assert.equal(absentResult.executed, false);
    assert.deepEqual(readJsonl(artifactPath), []);

    const allowedEngine = createEngine();
    allowedEngine.step("use calendar_admin");
    const allowedResult = await runLiveModelTurn({
      userIntent: USER_INTENT,
      authoritativeState: allowedEngine.state,
      artifactPath
    });

    if (allowedResult.selectedToolName !== "calendar_admin_create_event") {
      throw new Error(
        "Protected tool was exposed but the live model did not select " +
          "`calendar_admin_create_event`. " +
          `Selected tool: ${JSON.stringify(allowedResult.selectedToolName)}. ` +
          "This opt-in validation requires the model to exercise the protected tool path explicitly."
      );
    }

    assert.equal(allowedResult.protectedToolExposed, true);
    assert.equal(allowedResult.executed, true);
    assert.equal(readJsonl(artifactPath).length, 1);

    const clarifyResult = await runLiveModelTurn({
      userIntent: USER_INTENT,
      authoritativeState: allowedEngine.state,
      compilerInput: "prohibit calendar_admin",
      artifactPath
    });

    assert.equal(clarifyResult.decisionKind, "clarify");
    assert.equal(clarifyResult.executed, false);
    assert.equal(readJsonl(artifactPath).length, 1);
  }
);
