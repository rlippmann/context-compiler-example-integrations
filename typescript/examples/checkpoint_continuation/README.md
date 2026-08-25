# Checkpoint continuation

Restoring saved compiler state lets a fresh host process continue from the same
authoritative state. This example shows the 0.9 JSON state format in a generic
TypeScript travel-booking flow.

## Domain

The domain is a small travel-booking change flow.

The user requests a change from the current itinerary to a new itinerary.
The compiler rejects a replacement unless the old itinerary already has an
active `use` policy.

## Runtime

This is a generic TypeScript example.

It does not call an LLM.

It does not use directive drafter.

## What Context Compiler owns

Context Compiler owns:

- authoritative policy state
- the JSON state snapshot that captures it

Context Compiler 0.9 does not expose pending clarification or confirmation
state. A saved state restores only premise and policy data.

## What the host owns

The host owns:

- the booking record
- checkpoint persistence
- request/process boundaries
- the runtime behavior that actually applies the itinerary change

The host reads authoritative Context Compiler state after confirmation and
decides whether to apply the booking change.

## Why this is not prompt reinjection

This example does not re-send hidden instructions to a model.

The observable behavior change is host-side: the booking record changes only
after a restored engine resumes the pending confirmation and authoritative
state changes.

## Example behavior

1. The host starts with a booking on `boston_trip`.
2. The user initiates a switch to `chicago_trip`.
3. Context Compiler returns a semantic error because `boston_trip` is not active.
4. The host exports and persists the unchanged JSON state.
5. A fresh host process restores that state into a new engine.
6. A later `yes` input is `no_directive`; it does not resolve a pending change.

## Install

```shell
cd typescript/examples/checkpoint_continuation
npm install
```

## Validate

```shell
cd typescript/examples/checkpoint_continuation
npm run build
npm run typecheck
npm test
```

## Related integrations

The generic example teaches checkpoint continuation without requiring a
framework.

Related runtime surfaces:

- [typescript/starter_apps/node/README.md](../../starter_apps/node/README.md)
- [typescript/starter_apps/nextjs/README.md](../../starter_apps/nextjs/README.md)
