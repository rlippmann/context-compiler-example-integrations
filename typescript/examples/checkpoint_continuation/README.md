# State persistence

Persisting authoritative compiler state lets a fresh host process recover the
same premise and policy decisions without recreating them from model output or
conversation history. This example shows state persistence in a deterministic
TypeScript travel-booking flow.

## Domain

The host starts with a booking on `boston_trip`. The user selects
`chicago_trip`, Context Compiler records that selection in authoritative state,
and the host later applies the booking change from a restored engine.

## Runtime

This example does not call an LLM or use Directive Drafter.

## What Context Compiler owns

Context Compiler owns:

- authoritative policy state;
- serialization through `export_json()`;
- restoration through `import_json()`.

## What the host owns

The host owns:

- the booking record;
- persisted state storage;
- the process boundary;
- runtime behavior that applies the itinerary change.

The host reads restored authoritative policy state before applying the booking
change. Context Compiler remains the sole authority over premise and policy
state.

## Example behavior

1. The host submits `use chicago_trip`.
2. Context Compiler updates authoritative state.
3. The host persists that state JSON.
4. A fresh engine restores the saved JSON.
5. The host reads the restored `use` policy and applies the booking change from
   `boston_trip` to `chicago_trip`.

This example does not implement pending clarification, confirmation,
continuation, or resume semantics. The observable effect comes directly from
restored authoritative state.

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
