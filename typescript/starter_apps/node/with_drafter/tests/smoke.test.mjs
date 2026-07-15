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
    sessionId: "node-drafter-clarify",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.equal(typeof result.payload.promptToUser, "string");
  assert.ok(!("output" in result.payload));
  assert.ok(!("systemPrompt" in result.payload));
});

test("repeated sessionId persists checkpoint behavior across turns", async () => {
  const sessionId = "node-drafter-persist";
  const first = await handleChatBody({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.payload.kind, "clarify");

  const second = await handleChatBody({ sessionId, input: "yes" });
  assert.equal(second.payload.kind, "continue");
  assert.match(second.payload.systemPrompt, /USE: podman/);
});

test("historical messages stay downstream-only and do not mutate compiler state", async () => {
  const result = await handleChatBody({
    sessionId: "node-drafter-history",
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "use peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "continue");
  assert.match(result.payload.systemPrompt, /USE: peanuts/);
  assert.doesNotMatch(result.payload.systemPrompt, /PROHIBIT: peanuts/);
});

test("directive input can become compiler input before engine.step", async () => {
  const result = await handleChatBody({
    sessionId: "node-drafter-directive",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.match(result.payload.promptToUser, /podman/i);
  assert.doesNotMatch(result.payload.promptToUser, /docker/i);
});

test("drafter runs only for current input, not historical messages", async () => {
  const result = await handleChatBody({
    sessionId: "node-drafter-current-only",
    history: [{ role: "user", content: "use podman instead of docker" }],
    input: "set premise to concise replies"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.match(result.payload.promptToUser, /set premise concise replies/i);
  assert.doesNotMatch(result.payload.promptToUser, /podman/i);
});

test("pending clarification bypasses drafting and reuses pending prompt", async () => {
  const sessionId = "node-drafter-bypass";
  const first = await handleChatBody({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.payload.kind, "clarify");

  const second = await handleChatBody({ sessionId, input: "set premise to concise replies" });
  assert.equal(second.payload.kind, "clarify");
  assert.equal(second.payload.promptToUser, first.payload.promptToUser);
});

test("pending clarification survives checkpoint restore and later current-turn confirmation resolves it", async () => {
  const sessionId = "node-drafter-checkpoint-clarify";
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

test("unknown or unsafe drafter output falls back to raw input", async () => {
  const result = await handleChatBody({
    sessionId: "node-drafter-unsafe",
    input: "set premise to concise replies"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.match(result.payload.promptToUser, /set premise concise replies/i);
});

test("compound directives stay local and ask for separate inputs", async () => {
  const result = await handleChatBody({
    sessionId: "node-drafter-compound",
    input: "use docker and prohibit peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.payload.kind, "clarify");
  assert.match(result.payload.promptToUser, /multiple directives/i);
  assert.match(result.payload.promptToUser, /submit each directive separately/i);
});
