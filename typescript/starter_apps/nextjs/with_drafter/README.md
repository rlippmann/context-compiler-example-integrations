# Next.js starter app: with_drafter

Minimal Next.js App Router starter with one `/api/chat` route and an optional
directive-drafter layer before the compiler.

This variant uses the current example-integrations starter app as its source
material. The enforcement point is still request construction: the route
restores saved state, validates drafted directive input, and builds the request
payload the host would send onward.

This starter uses `@rlippmann/context-compiler-directive-drafter@^0.1.2`.

## Files

- [app/api/chat/route.ts](app/api/chat/route.ts) - route handler with safe drafter handoff
- [lib/context-sessions.ts](lib/context-sessions.ts) - in-memory checkpoint storage for the example
- [app/page.tsx](app/page.tsx) - minimal page that explains the API

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

## Request construction rule

The returned `requestPayload.systemPrompt` makes both kinds of authoritative
state visible:

- `PREMISE` is authoritative factual or request context
- `POLICIES` are explicit behavioral constraints

Example:

```text
You are an assistant operating under compiled context.

PREMISE:
draft is a board update summarizing quarterly results

POLICIES:
- USE: concise_style

Follow these constraints strictly.
```
