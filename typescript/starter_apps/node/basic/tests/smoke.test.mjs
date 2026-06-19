import assert from "node:assert/strict";
import test from "node:test";

import { handleChatBody } from "../server.ts";

test("missing sessionId or input returns validation error", async () => {
  const result = await handleChatBody({ input: "hello" });
  assert.equal(result.status, 400);
  assert.deepEqual(result.payload, { error: "sessionId and input are required" });
});

test("clarify returns no downstream output", async () => {
  const result = await handleChatBody({
    sessionId: "node-basic-clarify",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.equal(typeof result.payload.promptToUser, "string");
  assert.ok(!("output" in result.payload));
  assert.ok(!("systemPrompt" in result.payload));
});

test("repeated sessionId persists checkpoint behavior across turns", async () => {
  const sessionId = "node-basic-persist";
  const first = await handleChatBody({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.payload.kind, "clarify");

  const second = await handleChatBody({ sessionId, input: "yes" });
  assert.equal(second.payload.kind, "continue");
  assert.match(second.payload.systemPrompt, /USE: podman/);
});

test("history replay works when no saved checkpoint exists", async () => {
  const result = await handleChatBody({
    sessionId: "node-basic-history",
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "use peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.match(result.payload.promptToUser, /prohibited/i);
});
