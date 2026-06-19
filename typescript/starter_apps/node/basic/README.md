# Node starter app: basic

Small Node HTTP server showing the compiler-only starter flow.

This variant was adapted from the last `examples/integrations/node-basic`
version in `context-compiler-ts`, using the old compiler-only request flow as
source material while keeping this repo's current stand-in response style.

`@rlippmann/context-compiler` is enough here. Raw user input goes straight to
`engine.step(...)`, the compiler decides whether to update state or return
`clarify`, and the host continues normally.

No directive-drafter dependency is used in this variant.

## Files

- [server.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/basic/server.ts) - minimal chat endpoint with checkpoint persistence
- [package.json](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/basic/package.json) - compiler-only package dependencies

## Install

```bash
cd typescript/starter_apps/node/basic
npm install
```

## Run

```bash
npm run dev
```

The server listens on `http://127.0.0.1:8080/chat`.

## Smoke test

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H 'content-type: application/json' \
  -d '{"sessionId":"demo","input":"keep replies concise"}'
```

Expected response shape:

```json
{
  "kind": "continue",
  "output": "Normal host workflow would continue here. This compiler-only variant returns the compiled prompt instead of calling a live model.",
  "systemPrompt": "You are an assistant operating under compiled context.\n..."
}
```

Checkpoints use `exportCheckpointJson()` and `importCheckpointJson()`. That
preserves saved state and pending `clarify` or `confirm` state across requests.
