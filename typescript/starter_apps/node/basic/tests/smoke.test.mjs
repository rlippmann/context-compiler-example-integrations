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

test("historical messages stay downstream-only and do not mutate compiler state", async () => {
  const result = await handleChatBody({
    sessionId: "node-basic-history",
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "use peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "continue");
  assert.match(result.payload.systemPrompt, /USE: peanuts/);
  assert.doesNotMatch(result.payload.systemPrompt, /PROHIBIT: peanuts/);
});

test("pending clarification survives checkpoint restore and resolves on later current turn", async () => {
  const sessionId = "node-basic-checkpoint-clarify";
  const first = await handleChatBody({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.payload.kind, "clarify");

  const second = await handleChatBody({
    sessionId,
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "yes"
  });
  assert.equal(second.payload.kind, "continue");
  assert.match(second.payload.systemPrompt, /USE: podman/);
  assert.doesNotMatch(second.payload.systemPrompt, /PROHIBIT: peanuts/);
});
