# TypeScript examples

This package will publish TypeScript example integrations organized by
enforcement point first.

Open this section when you want small TypeScript examples that show a runtime
behavior change from authoritative state.

Start with a generic example README below if you want the clearest explanation
of an enforcement point before looking at starter apps.

Current generic TypeScript examples include:

- [typescript/examples/checkpoint_continuation/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/checkpoint_continuation/README.md)
- [typescript/examples/execution_authorization/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/execution_authorization/README.md)
- [typescript/examples/gateway_middleware/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/gateway_middleware/README.md)
- [typescript/examples/prompt_construction/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/prompt_construction/README.md)
- [typescript/examples/retrieval_filtering/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/retrieval_filtering/README.md)
- [typescript/examples/schema_selection/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/schema_selection/README.md)
- [typescript/examples/tool_gating/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/typescript/examples/tool_gating/README.md)

These generic examples are the main starting point for new readers.

They are the most direct way to see the enforcement point before any framework
or app runtime details.

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

Choose TypeScript when you want:

- generic examples in TypeScript with the same enforcement-point taxonomy
- minimal starter apps that show host/runtime boundaries
- a direct path into Node or Next.js-oriented examples
