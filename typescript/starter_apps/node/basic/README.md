# Node starter app: basic

Small Node HTTP server showing the compiler-only starter flow.

This variant was adapted from the last standalone TypeScript core
`examples/integrations/node-basic` example, using the old compiler-only
request flow as source material while keeping this repo's current stand-in
response style.

`@rlippmann/context-compiler` is enough here. Raw user input goes straight to
`engine.step(...)`, which returns an update, a semantic `error`, or
`no_directive`, and the host continues normally when no error occurs.

No directive-drafter dependency is used in this variant.

## Files

- [server.ts](server.ts) - minimal chat endpoint with checkpoint persistence
- [package.json](package.json) - compiler-only package dependencies

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

Saved state uses `export_json()` and `import_json()`. Context Compiler 0.9
persists premise and policy state across requests; it does not persist pending
clarification or confirmation state.
