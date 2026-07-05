import assert from "node:assert/strict";
import test from "node:test";
import { createEngine } from "@rlippmann/context-compiler";

import { runLiveGenerateObject } from "../src/live_model.js";

const RUN_LIVE_MODEL_ENV_VAR = "RUN_VERCEL_AI_SDK_LIVE_MODEL";
const USER_PROMPT = "Customer customer-123 says: I need help with order A-100.";

test(
  "live model generateObject output changes with authoritative schema selection",
  { skip: process.env[RUN_LIVE_MODEL_ENV_VAR] !== "1" },
  async () => {
    const absentResult = await runLiveGenerateObject({
      prompt: USER_PROMPT
    });

    assert.deepEqual(absentResult, {
      called: false,
      schemaName: null,
      object: null
    });

    const refundEngine = createEngine();
    refundEngine.step("use refund_intake");

    const refundResult = await runLiveGenerateObject({
      prompt: USER_PROMPT,
      authoritativeState: refundEngine.state
    });

    assert.equal(refundResult.called, true);
    assert.equal(refundResult.schemaName, "refund_intake");
    assertRefundIntakeObject(refundResult.object);

    const supportEngine = createEngine();
    supportEngine.step("use technical_support");

    const supportResult = await runLiveGenerateObject({
      prompt: USER_PROMPT,
      authoritativeState: supportEngine.state
    });

    assert.equal(supportResult.called, true);
    assert.equal(supportResult.schemaName, "technical_support");
    assertTechnicalSupportObject(supportResult.object);
  }
);

function assertRefundIntakeObject(
  value: unknown
): asserts value is {
  kind: "refund";
  customerId: string;
  orderId: string;
  reason: string;
} {
  assert.equal(typeof value, "object");
  assert.ok(value !== null);
  const record = value as Record<string, unknown>;
  assert.equal(record.kind, "refund");
  assert.equal(typeof record.customerId, "string");
  assert.equal(typeof record.orderId, "string");
  assert.equal(typeof record.reason, "string");
}

function assertTechnicalSupportObject(
  value: unknown
): asserts value is {
  kind: "technical_support";
  customerId: string;
  issue: string;
} {
  assert.equal(typeof value, "object");
  assert.ok(value !== null);
  const record = value as Record<string, unknown>;
  assert.equal(record.kind, "technical_support");
  assert.equal(typeof record.customerId, "string");
  assert.equal(typeof record.issue, "string");
}
