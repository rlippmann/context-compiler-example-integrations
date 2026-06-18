# Next.js starter app

This starter app keeps the example small: a minimal Next.js App Router project
with a single `/api/chat` route and a tiny landing page.

The enforcement point is request construction and context assembly. The route
restores authoritative state, optionally drafts a directive candidate, and then
builds the request payload the host would send onward.

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

- `@rlippmann/context-compiler-directive-drafter` drafts a candidate directive from raw input
- `@rlippmann/context-compiler` decides whether that directive can change authoritative state
- the route falls back to the original input on `no_directive`, `unknown`, or validation failure

This example intentionally avoids a full chat UI. The useful behavior here is
the server-side boundary between drafted input and authoritative request
construction.
