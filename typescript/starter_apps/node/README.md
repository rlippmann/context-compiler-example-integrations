# Node starter app

This starter app shows a small Node HTTP server with one enforcement point:
execution authorization before the host calls its normal assistant workflow.

`@rlippmann/context-compiler-directive-drafter` helps the host recognize
directive-shaped input. `@rlippmann/context-compiler` remains the only layer
that can accept or reject state changes and mutate authoritative state.

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

Some sandboxed CI or agent environments disallow opening local listening
sockets and may fail with `listen EPERM` even when the example code is valid.
When that happens, treat `npm run typecheck` as the available validation inside
that environment and run the HTTP smoke test on a normal local machine.

## Host flow

1. Restore the saved compiler checkpoint for the session.
2. If the engine has a pending clarification, bypass drafting and pass the raw user input directly to `engine.step(...)`.
3. Otherwise run `preprocessHeuristic(userInput)`.
4. If the drafter returns a directive candidate, validate it with `parsePreprocessorOutput(...)`.
5. Pass only validated directive text to `engine.step(...)`.
6. Fall back to the original user input when the drafter returns no directive, unknown, or an invalid candidate.

This keeps acquisition non-authoritative. The host still behaves safely if the
drafter fails, abstains, or is replaced with an adversarial stub.
