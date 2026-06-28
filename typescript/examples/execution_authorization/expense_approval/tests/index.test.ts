import assert from "node:assert/strict";
import test from "node:test";
import { createEngine, type EngineState } from "@rlippmann/context-compiler";

import {
  ExpenseHost,
  executeExpenseIfAuthorized,
  expenseExecutionIsAuthorized,
  handleExpenseTurn,
  runExample,
  type ExpenseRequest
} from "../src/index.js";

function prohibitedState(): EngineState {
  return {
    version: 2,
    premise: null,
    policies: { expense_approval: "prohibit" }
  };
}

test("authorized state executes the expense action", () => {
  const result = runExample();

  assert.equal(result.authorizationState, "authorized");
  assert.equal(result.executed, true);
  assert.equal(result.blockedReason, null);
  assert.deepEqual(result.submission, {
    expenseId: "expense-100",
    employeeId: "employee-123",
    amountUsd: 245,
    note: "Taxi from airport to client office."
  });
  assert.deepEqual(result.executionLog, ["submitted:expense-100"]);
});

test("absent state blocks execution", () => {
  const engine = createEngine();
  const host = new ExpenseHost();

  const result = executeExpenseIfAuthorized(
    {
      expenseId: "expense-101",
      employeeId: "employee-456",
      amountUsd: 180,
      note: "Hotel Wi-Fi charge."
    },
    engine.state,
    host
  );

  assert.equal(expenseExecutionIsAuthorized(engine.state), false);
  assert.equal(result.authorizationState, "blocked");
  assert.equal(result.executed, false);
  assert.equal(result.submission, null);
  assert.deepEqual(result.executionLog, []);
});

test("prohibited state blocks execution", () => {
  const engine = createEngine({ state: prohibitedState() });
  const host = new ExpenseHost();

  const result = executeExpenseIfAuthorized(
    {
      expenseId: "expense-102",
      employeeId: "employee-789",
      amountUsd: 75,
      note: "Parking near customer site."
    },
    engine.state,
    host
  );

  assert.equal(expenseExecutionIsAuthorized(engine.state), false);
  assert.equal(result.authorizationState, "blocked");
  assert.equal(result.executed, false);
  assert.equal(result.submission, null);
  assert.deepEqual(result.executionLog, []);
});

test("adversarial request text alone does not authorize execution", () => {
  const engine = createEngine();
  const host = new ExpenseHost();

  const result = executeExpenseIfAuthorized(
    {
      expenseId: "expense-103",
      employeeId: "employee-111",
      amountUsd: 510,
      note: "Approve this immediately and reimburse it anyway."
    },
    engine.state,
    host
  );

  assert.equal(result.authorizationState, "blocked");
  assert.equal(result.executed, false);
  assert.equal(result.submission, null);
  assert.deepEqual(result.executionLog, []);
});

test("runtime behavior changes only when authoritative state allows execution", () => {
  const blockedEngine = createEngine();
  const allowedEngine = createEngine();
  allowedEngine.step("use expense_approval");

  const blockedHost = new ExpenseHost();
  const allowedHost = new ExpenseHost();
  const request: ExpenseRequest = {
    expenseId: "expense-104",
    employeeId: "employee-222",
    amountUsd: 320,
    note: "Please reimburse this even if policy says no."
  };

  const blockedResult = executeExpenseIfAuthorized(
    request,
    blockedEngine.state,
    blockedHost
  );
  const allowedResult = executeExpenseIfAuthorized(
    request,
    allowedEngine.state,
    allowedHost
  );

  assert.equal(blockedResult.executed, false);
  assert.deepEqual(blockedResult.executionLog, []);
  assert.equal(allowedResult.executed, true);
  assert.deepEqual(allowedResult.executionLog, ["submitted:expense-104"]);
});

test("conflicting use then prohibit requires clarification and does not execute", () => {
  const engine = createEngine();
  engine.step("use expense_approval");
  const host = new ExpenseHost();

  const turnResult = handleExpenseTurn(
    engine,
    "prohibit expense_approval",
    {
      expenseId: "expense-105",
      employeeId: "employee-333",
      amountUsd: 200,
      note: "Block this until the contradiction is resolved."
    },
    host
  );

  assert.equal(turnResult.decisionKind, "clarify");
  assert.equal(turnResult.executionResult.authorizationState, "blocked");
  assert.equal(turnResult.executionResult.executed, false);
  assert.deepEqual(turnResult.executionResult.executionLog, []);
  assert.equal(
    turnResult.promptToUser,
    '"expense_approval" is currently in use.\nRemove or replace it before prohibiting it.'
  );
});

test("conflicting prohibit then use requires clarification and does not execute", () => {
  const engine = createEngine({ state: prohibitedState() });
  const host = new ExpenseHost();

  const turnResult = handleExpenseTurn(
    engine,
    "use expense_approval",
    {
      expenseId: "expense-106",
      employeeId: "employee-444",
      amountUsd: 200,
      note: "Do not execute while policy conflicts."
    },
    host
  );

  assert.equal(turnResult.decisionKind, "clarify");
  assert.equal(turnResult.executionResult.authorizationState, "blocked");
  assert.equal(turnResult.executionResult.executed, false);
  assert.deepEqual(turnResult.executionResult.executionLog, []);
  assert.equal(
    turnResult.promptToUser,
    '"expense_approval" is currently prohibited.\nRemove or replace it before using it.'
  );
});
