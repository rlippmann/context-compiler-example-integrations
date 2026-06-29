# Checkpoint continuation

This example demonstrates checkpoint continuation as an enforcement point.

## Domain

The domain is a small travel-booking change flow.

The user requests a change from the current itinerary to a new itinerary.
That change requires confirmation before the host applies it.

## Runtime

This is a generic TypeScript example.

It does not call an LLM.

It does not use directive drafter.

## What Context Compiler owns

Context Compiler owns:

- authoritative policy state
- the pending confirmation continuation state
- the checkpoint that captures both

In this example, the pending checkpoint state is what makes the resumed
confirmation meaningful.

Restoring authoritative state alone is not enough to resume the pending change.

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
3. Context Compiler enters a pending confirmation state.
4. The host exports and persists the checkpoint.
5. A fresh host process restores that checkpoint into a new engine.
6. If the user confirms, the host applies the itinerary change.
7. If the user rejects or sends unrelated text, the booking remains unchanged.

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

- [python/examples/checkpoint_continuation/fastapi/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/checkpoint_continuation/fastapi/README.md)
- [typescript/starter_apps/node/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/README.md)
- [typescript/starter_apps/nextjs/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/README.md)
