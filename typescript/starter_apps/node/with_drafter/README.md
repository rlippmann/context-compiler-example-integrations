# Node starter app: with_drafter

Small Node HTTP server showing the optional acquisition layer before the
compiler.

This variant uses the current example-integrations starter app as its source
material. `@rlippmann/context-compiler-directive-drafter` can help recognize
directive-shaped input, but the compiler remains the only authority over saved
state.

This starter uses `@rlippmann/context-compiler-directive-drafter@^0.1.2`.

## Files

- [server.ts](server.ts) - minimal chat endpoint with checkpoint persistence and drafter handoff
- [package.json](package.json) - package dependencies for the optional drafter layer

## Install

```bash
cd typescript/starter_apps/node/with_drafter
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
  "output": "Normal host workflow would continue here. This example returns the compiled prompt instead of calling a live model.",
  "systemPrompt": "You are an assistant operating under compiled context.\n..."
}
```

If you use directive-drafter, the host validates drafted output before passing
it to the compiler and falls back to raw input when drafting fails, abstains,
or returns `unknown`.
