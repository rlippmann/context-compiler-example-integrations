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
  engine.step("use python_script");
  engine.step("prohibit shell_command");

  const selected = selectStructuredSchemasFromState(engine.state);

  assert.deepEqual(
    selected.map((schema) => schema.name),
    ["python_script"]
  );
});

test("selected schema becomes generateObject request config", () => {
  const engine = createEngine();
  engine.step("use python_script");

  const request = buildGenerateObjectRequest(
    engine.state,
    "Write a short Python script that prints hello."
  );

  assert.ok(request !== null);
  assert.equal(request.schemaName, "python_script");
  assert.equal(
    request.schema.schema.safeParse({ code: "print('hello')" }).success,
    true
  );
});

test("omit schema when state does not authorize one", async () => {
  const engine = createEngine();
  engine.step("prohibit python_script");
  engine.step("prohibit shell_command");

  const request = buildGenerateObjectRequest(
    engine.state,
    "Write a short Python script that prints hello."
  );
  let called = false;
  const result = await generateStructuredObject(engine.state, "ignored", async () => {
    called = true;
    return { object: { code: "print('hello')" } };
  });

  assert.equal(request, null);
  assert.equal(result, null);
  assert.equal(called, false);
});
