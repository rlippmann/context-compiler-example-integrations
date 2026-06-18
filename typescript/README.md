# TypeScript examples

TypeScript examples in this repo stay organized by enforcement point first.

Starter apps are available when a small runnable host makes the enforcement
point easier to see:

- [starter_apps/node](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/README.md) - execution authorization starter with a small Node HTTP server
- [starter_apps/nextjs](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/README.md) - request construction and context assembly starter with a minimal Next.js App Router app

In these starters:

- `@rlippmann/context-compiler` is the authority layer
- `@rlippmann/context-compiler-directive-drafter` is optional help for recognizing directive-shaped input

The compiler-only flow is always the baseline. If a starter includes
directive-drafter, it is there to help acquisition, not to own state changes.
