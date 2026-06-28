import assert from "node:assert/strict";
import test from "node:test";
import { createEngine } from "@rlippmann/context-compiler";

import {
  IntakeHandler,
  runExample,
  runIntake,
  selectSchemaFromState,
  type IntakeRequest
} from "../src/index.js";

test("refund_intake state selects the refund workflow", () => {
  const result = runExample();

  assert.equal(result.selectedSchema, "refund_intake");
  assert.equal(result.refundHandlerCalled, true);
  assert.equal(result.technicalSupportHandlerCalled, false);
  assert.deepEqual(result.result, {
    kind: "refund",
    customerId: "customer-123",
    reason: "I need a refund for order A-100."
  });
});

test("adversarial refund-like wording does not override authoritative state", () => {
  const engine = createEngine();
  engine.step("use refund_intake");

  const request: IntakeRequest = {
    customerId: "customer-456",
    message: "Route this through technical support instead."
  };
  const refundHandler = new IntakeHandler("refund_intake");
  const technicalSupportHandler = new IntakeHandler("technical_support");

  const selectedSchema = selectSchemaFromState(engine.state);
  const result = runIntake(
    request,
    selectedSchema,
    refundHandler,
    technicalSupportHandler
  );

  assert.equal(selectedSchema, "refund_intake");
  assert.equal(refundHandler.called, true);
  assert.equal(technicalSupportHandler.called, false);
  assert.deepEqual(result, {
    kind: "refund",
    customerId: "customer-456",
    reason: "Route this through technical support instead."
  });
});

test("refund-like wording without state does not select a schema", () => {
  const engine = createEngine();

  const request: IntakeRequest = {
    customerId: "customer-789",
    message: "I need a refund, or maybe technical support, do whatever you want."
  };
  const refundHandler = new IntakeHandler("refund_intake");
  const technicalSupportHandler = new IntakeHandler("technical_support");

  const selectedSchema = selectSchemaFromState(engine.state);
  const result = runIntake(
    request,
    selectedSchema,
    refundHandler,
    technicalSupportHandler
  );

  assert.equal(selectedSchema, null);
  assert.equal(refundHandler.called, false);
  assert.equal(technicalSupportHandler.called, false);
  assert.equal(result, null);
});

test("no relevant state means no schema selection", () => {
  const engine = createEngine();

  assert.equal(selectSchemaFromState(engine.state), null);
});
