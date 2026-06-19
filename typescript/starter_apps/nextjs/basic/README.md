# Next.js starter app: basic

Minimal Next.js App Router starter with one `/api/chat` route and no
directive-drafter dependency.

This variant was adapted from the last `examples/integrations/nextjs-basic`
version in `context-compiler-ts`, using the old compiler-only route flow as
source material while keeping this repo's request-payload stand-in.

The enforcement point is request construction. The route restores saved state,
runs the compiler, and builds the request payload the host would send onward.

## Files

- [app/api/chat/route.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/basic/app/api/chat/route.ts) - compiler-only route handler
- [lib/context-sessions.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/basic/lib/context-sessions.ts) - in-memory checkpoint storage for the example
- [app/page.tsx](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/basic/app/page.tsx) - minimal page that explains the API

## Install

```bash
cd typescript/starter_apps/nextjs/basic
npm install
```

## Run

```bash
npm run dev
```

Then open `http://localhost:3000` or POST to `http://localhost:3000/api/chat`.

## Boundary

- `@rlippmann/context-compiler` owns authoritative state changes
- no directive-drafter package is used in this variant
- the route returns the request payload instead of calling a live model

Checkpoints use `exportCheckpointJson()` and `importCheckpointJson()`. That
preserves saved state and pending `clarify` or `confirm` state across stateless
requests.
