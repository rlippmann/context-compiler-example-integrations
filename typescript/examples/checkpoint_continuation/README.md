# Compiler state persistence

This example shows how a TypeScript host persists and restores the
authoritative Context Compiler 0.9 state in a travel-booking flow.

## Domain

The host starts with a booking on `boston_trip`. A request to replace it with
`chicago_trip` is submitted as a compiler directive.

Because `boston_trip` is not already active under a `use` policy, Context
Compiler returns a semantic error and leaves authoritative state unchanged.

## Runtime

This example does not call an LLM or use directive drafter. The host exports
the compiler JSON state, restores it into a fresh engine, and verifies that the
same premise and policies are available after the process boundary.

Context Compiler 0.9 does not expose persisted pending clarification or
confirmation state. This example does not implement a replacement continuation
mechanism.

## What Context Compiler owns

Context Compiler owns:

- authoritative premise and policy state;
- semantic validation of the submitted directive;
- the JSON state representation used for persistence.

## What the host owns

The host owns:

- the booking record;
- checkpoint storage and process boundaries;
- any later workflow that might act on the restored state.

The example does not apply a booking change after the semantic error. No host
state change is implied by restoring the compiler state.

## Example behavior

1. The host submits `use chicago_trip instead of boston_trip`.
2. The compiler returns a semantic `error` because `boston_trip` is not active.
3. The host persists the unchanged JSON state with `export_json()`.
4. A fresh engine restores that JSON with `import_json()`.
5. The restored premise and policies match the original authoritative state.

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
