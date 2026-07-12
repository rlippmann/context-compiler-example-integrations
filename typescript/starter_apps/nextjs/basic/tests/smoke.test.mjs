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
    sessionId: "nextjs-basic-clarify",
    input: "use podman instead of docker"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "clarify");
  assert.equal(typeof result.json.promptToUser, "string");
  assert.ok(!("requestPayload" in result.json));
  assert.ok(!("output" in result.json));
});

test("repeated sessionId persists checkpoint behavior across turns", async () => {
  const sessionId = "nextjs-basic-persist";
  const first = await postJson({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.json.kind, "clarify");

  const second = await postJson({ sessionId, input: "yes" });
  assert.equal(second.json.kind, "continue");
  assert.equal(typeof second.json.requestPayload?.systemPrompt, "string");
  assert.match(second.json.requestPayload.systemPrompt, /USE: podman/);
});

test("historical messages stay downstream-only and do not mutate compiler state", async () => {
  const result = await postJson({
    sessionId: "nextjs-basic-history",
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "use peanuts"
  });

  assert.equal(result.status, 200);
  assert.equal(result.json.kind, "continue");
  assert.match(result.json.requestPayload.systemPrompt, /USE: peanuts/);
  assert.doesNotMatch(result.json.requestPayload.systemPrompt, /PROHIBIT: peanuts/);
  assert.deepEqual(result.json.requestPayload.history, [{ role: "user", content: "prohibit peanuts" }]);
});

test("pending clarification survives checkpoint restore and resolves on later current turn", async () => {
  const sessionId = "nextjs-basic-checkpoint-clarify";
  const first = await postJson({ sessionId, input: "use podman instead of docker" });
  assert.equal(first.json.kind, "clarify");

  const second = await postJson({
    sessionId,
    history: [{ role: "user", content: "prohibit peanuts" }],
    input: "yes"
  });
  assert.equal(second.status, 200);
  assert.equal(second.json.kind, "continue");
  assert.match(second.json.requestPayload.systemPrompt, /USE: podman/);
  assert.doesNotMatch(second.json.requestPayload.systemPrompt, /PROHIBIT: peanuts/);
});

test("saved premise appears in returned system prompt", async () => {
  const sessionId = "nextjs-basic-premise";
  const first = await postJson({
    sessionId,
    input: "set premise draft is a board update summarizing quarterly results"
  });
  assert.equal(first.json.kind, "continue");

  const second = await postJson({
    sessionId,
    input: "Revise this update."
  });
  assert.equal(second.json.kind, "continue");
  assert.match(
    second.json.requestPayload.systemPrompt,
    /PREMISE:\ndraft is a board update summarizing quarterly results/
  );
});
