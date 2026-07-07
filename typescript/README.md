# TypeScript examples

These examples show how saved premise and policy change what a host allows,
routes, retrieves, builds, or executes at runtime.

Examples are organized by enforcement point first.

The core library lives in
[`context-compiler-ts`](https://github.com/rlippmann/context-compiler-ts).
Directive recognition can be added with
[`context-compiler-directive-drafter-ts`](https://github.com/rlippmann/context-compiler-directive-drafter-ts),
but that layer is optional. This package is the examples and integration
patterns layer.

`context-compiler-ts` defines the authority contract.
`context-compiler-directive-drafter-ts` can optionally help acquire and draft
authority, but it is not the authority layer.
This examples package shows where authority is enforced.

Prompt reinjection influences model behavior.
Context Compiler influences runtime behavior.

## Generic examples

These generic examples are the main starting point for new readers.

Open the enforcement point that matches the runtime behavior you want to
inspect:

- [Checkpoint continuation](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/checkpoint_continuation/README.md): persisted confirmation and resume flows change host behavior across turns or requests
- [Execution authorization](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/execution_authorization/README.md): protected host actions execute only when authoritative state allows them
- [Gateway middleware](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/gateway_middleware/README.md): the host allows, blocks, or routes requests before downstream work runs
- [Prompt construction](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/prompt_construction/README.md): the host builds different request or prompt payloads from authoritative state
- [Retrieval filtering](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/retrieval_filtering/README.md): the host changes which documents are eligible or relevant before returning results
- [Schema selection](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/schema_selection/README.md): the host picks different workflow or response schemas from authoritative state
- [Tool gating](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/tool_gating/README.md): the host changes which tools are visible or executable at runtime

## Starter apps

Starter apps are available when a small runnable host makes the enforcement
point easier to see:

- [starter_apps/node](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/starter_apps/node/README.md) - execution authorization starter variants for a small Node HTTP server
- [starter_apps/nextjs](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/starter_apps/nextjs/README.md) - request construction and context assembly starter variants for a minimal Next.js App Router app

Open a starter app when you want a minimal host runtime around the enforcement
point instead of a generic example alone.

In these starters:

- `@rlippmann/context-compiler` is the authority layer
- `@rlippmann/context-compiler-directive-drafter` is optional help for recognizing directive-shaped input

Each starter app now comes in two variants:

- `basic` = compiler-only baseline with no directive-drafter dependency
- `with_drafter` = optional acquisition layer before the compiler

The compiler-only flow is always the baseline. If a starter includes
directive-drafter, it is there to help acquisition, not to own state changes.

## Run an example

To explore or run an example, use a repository checkout:

1. Clone
   [`context-compiler-example-integrations`](https://github.com/rlippmann/context-compiler-example-integrations).
2. Choose a generic example or a starter app.
3. Open that example's README.
4. Follow the example-specific setup, runtime, and validation instructions.
