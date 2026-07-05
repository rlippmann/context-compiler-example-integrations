# Vercel AI SDK `generateObject` schema selection

This example shows the TypeScript counterpart to the Python schema-selection
examples in this repository.

The enforcement point is schema selection.

Flow:

`compiler state -> host selects schema -> host builds generateObject request -> downstream model call`

## What this example demonstrates

- Compiler-only state drives host schema selection.
- The host chooses which structured-output schema to offer.
- `generateObject` is the downstream host behavior, not the authority layer.
- No model output mutates compiler state.
- If compiler state does not authorize a schema, the host omits schema selection.
- The provider-free tests are the canonical proof for this example.

## Boundary

- `@rlippmann/context-compiler` owns authoritative state transitions.
- The host reads compiler state and selects a Zod schema, or no schema.
- The host may pass that schema into Vercel AI SDK `generateObject`.
- The compiler does not select schemas dynamically.
- The compiler does not derive state from model output.

## Deterministic behavior

Given policy state:

```text
use refund_intake
prohibit technical_support
```

the host offers the `refund_intake` schema and does not offer the
`technical_support` schema.

If state prohibits every known schema, the host omits schema selection and does
not build a `generateObject` request.

## Test coverage

Tests assert:

- compiler state -> selected schema
- selected schema -> request config
- omit schema when state does not authorize one
- contradiction triggers clarification while preserving the previously
  authorized schema in current state

Primary tests are deterministic and do not call a model.

## Opt-in live-model validation

The example also includes an opt-in Tier 3 path that uses the real Vercel AI
SDK `generateObject` call with the same host-side schema selection logic.

Use the same prompt across states:

```text
Customer customer-123 says: I need help with order A-100.
```

What to observe:

- absent state: no schema is authorized, so the host does not call
  `generateObject`
- `use refund_intake`: the host selects the `refund_intake` schema and the live
  output has refund-intake shape
- `use technical_support`: the host selects the `technical_support` schema and
  the live output has technical-support shape

The live-model proof stays focused on absent, `refund_intake`, and
`technical_support` selection.

If you probe contradiction separately, the current deterministic behavior is:

- `use refund_intake` followed by `prohibit refund_intake` produces
  clarification from the compiler
- the previously authorized `refund_intake` schema remains selected in current
  state until that contradiction is resolved

## Install

```bash
cd typescript/examples/schema_selection/vercel_ai_sdk_generate_object
npm install
```

## Validate

```bash
npm run build
npm run typecheck
npm test
```

Run the opt-in live-model validation:

```bash
export RUN_VERCEL_AI_SDK_LIVE_MODEL=1
export OPENAI_API_KEY=...
export MODEL=gpt-4o-mini
npm test -- --test-name-pattern="live model generateObject output changes with authoritative schema selection"
```

Live-model contract:

- `OPENAI_API_KEY` is required
- `MODEL` defaults to `gpt-4o-mini`
- canonical provider-free tests remain the primary proof

## Run the example

```bash
npm run example
```

The example uses a stubbed `generateObject` implementation so the downstream
behavior stays observable without a live model.
