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

## Boundary

- `@rlippmann/context-compiler` owns authoritative state transitions.
- The host reads compiler state and selects a Zod schema, or no schema.
- The host may pass that schema into Vercel AI SDK `generateObject`.
- The compiler does not select schemas dynamically.
- The compiler does not derive state from model output.

## Deterministic behavior

Given policy state:

```text
use python_script
prohibit shell_command
```

the host offers the `python_script` schema and does not offer the
`shell_command` schema.

If state prohibits every known schema, the host omits schema selection and does
not build a `generateObject` request.

## Test coverage

Tests assert:

- compiler state -> selected schema
- selected schema -> request config
- omit schema when state does not authorize one

Primary tests are deterministic and do not call a model.

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

## Run the example

```bash
npm run example
```

The example uses a stubbed `generateObject` implementation so the downstream
behavior stays observable without a live model.
