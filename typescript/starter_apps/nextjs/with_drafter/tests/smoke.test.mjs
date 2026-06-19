import assert from "node:assert/strict";
import test from "node:test";

import { POST } from "../app/api/chat/route.ts";

async function postJson(body) {
  const response = await POST(
    new Request("http://localhost:3000/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    })
  );
  return {
    status: response.status,
    json: await response.json()
  };
}

test("missing sessionId or input returns validation error", async () => {
  const result = await postJson({ input: "hello" });
  assert.equal(result.status, 400);
  assert.deepEqual(result.json, { error: "sessionId and input are required" });
});

test("clarify returns no downstream request payload", async () => {
  const result = await postJson({
    sessionId: "nextjs-drafter-clarify",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "clarify");
  assert.equal(typeof result.json.promptToUser, "string");
  assert.ok(!("requestPayload" in result.json));
  assert.ok(!("output" in result.json));
});

test("repeated sessionId persists checkpoint behavior across turns", async () => {
  const sessionId = "nextjs-drafter-persist";
  const first = await postJson({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.json.kind, "clarify");

  const second = await postJson({ sessionId, input: "yes" });
  assert.equal(second.json.kind, "continue");
  assert.match(second.json.requestPayload.systemPrompt, /USE: podman/);
});

test("history replay works when no saved checkpoint exists", async () => {
  const result = await postJson({
    sessionId: "nextjs-drafter-history",
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "use peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "clarify");
  assert.match(result.json.promptToUser, /prohibited/i);
});

test("directive input can become compiler input before engine.step", async () => {
  const result = await postJson({
    sessionId: "nextjs-drafter-directive",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "clarify");
  assert.match(result.json.promptToUser, /podman/i);
  assert.doesNotMatch(result.json.promptToUser, /docker/i);
});

test("pending clarification bypasses drafting and reuses pending prompt", async () => {
  const sessionId = "nextjs-drafter-bypass";
  const first = await postJson({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.json.kind, "clarify");

  const second = await postJson({ sessionId, input: "set premise to concise replies" });
  assert.equal(second.json.kind, "clarify");
  assert.equal(second.json.promptToUser, first.json.promptToUser);
});

test("unknown or unsafe drafter output falls back to raw input", async () => {
  const result = await postJson({
    sessionId: "nextjs-drafter-unsafe",
    input: "set premise to concise replies"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "clarify");
  assert.match(result.json.promptToUser, /set premise concise replies/i);
});
