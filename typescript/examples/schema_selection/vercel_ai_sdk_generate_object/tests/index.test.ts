import test from "node:test";
import assert from "node:assert/strict";
import { createEngine } from "@rlippmann/context-compiler";

import {
  buildGenerateObjectRequest,
  generateStructuredObject,
  selectStructuredSchemasFromState
} from "../src/index.js";

test("compiler state selects only the authorized schema", () => {
  const engine = createEngine();
  engine.step("use refund_intake");
  engine.step("prohibit technical_support");

  const selected = selectStructuredSchemasFromState(engine.state);

  assert.deepEqual(
    selected.map((schema) => schema.name),
    ["refund_intake"]
  );
});

test("selected schema becomes generateObject request config", () => {
  const engine = createEngine();
  engine.step("use refund_intake");

  const request = buildGenerateObjectRequest(
    engine.state,
    "Customer customer-123 says: I need a refund for order A-100."
  );

  assert.ok(request !== null);
  assert.equal(request.schemaName, "refund_intake");
  assert.equal(
    request.schema.schema.safeParse({
      kind: "refund",
      customerId: "customer-123",
      orderId: "A-100",
      reason: "I need a refund for order A-100."
    }).success,
    true
  );
});

test("technical_support state becomes generateObject request config", () => {
  const engine = createEngine();
  engine.step("use technical_support");

  const request = buildGenerateObjectRequest(
    engine.state,
    "Customer customer-123 says the checkout page is broken."
  );

  assert.ok(request !== null);
  assert.equal(request.schemaName, "technical_support");
  assert.equal(
    request.schema.schema.safeParse({
      kind: "technical_support",
      customerId: "customer-123",
      issue: "The checkout page is broken."
    }).success,
    true
  );
});

test("omit schema when state does not authorize one", async () => {
  const engine = createEngine();
  engine.step("prohibit refund_intake");
  engine.step("prohibit technical_support");

  const request = buildGenerateObjectRequest(
    engine.state,
    "Customer customer-123 says: I need a refund for order A-100."
  );
  let called = false;
  const result = await generateStructuredObject(engine.state, "ignored", async () => {
    called = true;
    return {
      object: {
        kind: "refund",
        customerId: "customer-123",
        orderId: "A-100",
        reason: "I need a refund for order A-100."
      }
    };
  });

  assert.equal(request, null);
  assert.equal(result, null);
  assert.equal(called, false);
});

test("contradiction clarifies and preserves the previously authorized schema", () => {
  const engine = createEngine();
  engine.step("use refund_intake");

  const decision = engine.step("prohibit refund_intake");
  const request = buildGenerateObjectRequest(
    engine.state,
    "Customer customer-123 says: I need a refund for order A-100."
  );

  assert.equal(decision.kind, "clarify");
  assert.ok(request !== null);
  assert.equal(request.schemaName, "refund_intake");
});
