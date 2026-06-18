# Next.js starter app

Minimal Next.js App Router example with one `/api/chat` route and a small
landing page.

The enforcement point is request construction. The route restores saved state,
runs the compiler, and builds the request payload the host would send onward.

`@rlippmann/context-compiler` is useful by itself here. A host can pass raw
user input to `engine.step(...)` and continue through its normal downstream
model or application flow.

## Files

- [app/api/chat/route.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/app/api/chat/route.ts) - route handler with the safe drafter handoff
- [lib/context-sessions.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/lib/context-sessions.ts) - in-memory checkpoint storage for the example
- [app/page.tsx](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/app/page.tsx) - minimal page that explains the API

## Install

```bash
cd typescript/starter_apps/nextjs
npm install
```

## Run

```bash
npm run dev
```

Then open `http://localhost:3000` or POST to `http://localhost:3000/api/chat`.

## Boundary

- `@rlippmann/context-compiler` owns authoritative state changes
- `@rlippmann/context-compiler-directive-drafter` is optional help for recognizing directive-shaped input
- drafted output is validated before it reaches the compiler
- the route falls back to raw input on `no_directive`, `unknown`, or validation failure

This example intentionally stops at request construction instead of making a
real model call.

The returned `requestPayload` is the stand-in. It shows the compiled system
prompt, forwarded history, and raw user input.

Checkpoints use `exportCheckpointJson()` and `importCheckpointJson()`. That
preserves saved state and pending `clarify` or `confirm` state across stateless
requests.
