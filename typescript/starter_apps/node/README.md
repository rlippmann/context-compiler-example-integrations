# Node starter app

Small Node HTTP server showing execution authorization before the host continues
with its usual assistant flow.

`@rlippmann/context-compiler` works on its own here. The host can pass raw user
input to `engine.step(...)`, let the compiler decide whether to update state or
return `clarify`, and then continue normally.

This starter also includes the optional directive-drafter path.
`@rlippmann/context-compiler-directive-drafter` can help recognize
directive-shaped input, but the compiler remains the only authority over saved
state.

## Files

- [server.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/server.ts) - minimal chat endpoint with checkpoint persistence and drafter handoff
- [package.json](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/package.json) - published package dependencies only

## Install

```bash
cd typescript/starter_apps/node
npm install
```

## Run

```bash
npm run dev
```

The server listens on `http://127.0.0.1:8080/chat`.

## Smoke test

If the server is already running in one terminal:

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H 'content-type: application/json' \
  -d '{"sessionId":"demo","input":"keep replies concise"}'
```

Expected response shape:

```json
{
  "kind": "continue",
  "output": "Normal host workflow would continue here. This example returns the compiled prompt instead of calling a live model.",
  "systemPrompt": "You are an assistant operating under compiled context.\n..."
}
```

The response returns a compiled prompt as a stand-in for a real downstream
model call.

Checkpoints use `exportCheckpointJson()` and `importCheckpointJson()`. That
preserves saved state and pending `clarify` or `confirm` state across requests.

If you do use directive-drafter, the host validates drafted output before
passing it to the compiler and falls back to raw input when drafting fails,
abstains, or returns `unknown`.
