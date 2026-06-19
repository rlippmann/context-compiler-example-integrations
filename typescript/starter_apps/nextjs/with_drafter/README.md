# Next.js starter app: with_drafter

Minimal Next.js App Router starter with one `/api/chat` route and an optional
directive-drafter layer before the compiler.

This variant uses the current example-integrations starter app as its source
material. The enforcement point is still request construction: the route
restores saved state, validates drafted directive input, and builds the request
payload the host would send onward.

## Files

- [app/api/chat/route.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/with_drafter/app/api/chat/route.ts) - route handler with safe drafter handoff
- [lib/context-sessions.ts](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/with_drafter/lib/context-sessions.ts) - in-memory checkpoint storage for the example
- [app/page.tsx](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/with_drafter/app/page.tsx) - minimal page that explains the API

## Install

```bash
cd typescript/starter_apps/nextjs/with_drafter
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

The returned `requestPayload` is the stand-in. It shows the compiled system
prompt, forwarded history, and raw user input.
