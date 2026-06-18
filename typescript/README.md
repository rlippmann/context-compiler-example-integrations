# TypeScript examples

TypeScript examples in this repo stay organized by enforcement point first.

Starter apps are available when the example benefits from a small runnable host:

- [starter_apps/node](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/README.md) - execution authorization starter with a small Node HTTP server
- [starter_apps/nextjs](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/README.md) - request construction and context assembly starter with a minimal Next.js App Router app

Each starter app keeps the package boundary explicit:

- `@rlippmann/context-compiler` is the authority layer
- `@rlippmann/context-compiler-directive-drafter` is the acquisition and drafting layer

Examples in this track should:

- use explicit authoritative state
- validate drafted directive output before passing it to the compiler
- remain meaningful with an adversarial stub or failed drafter pass
- show an observable runtime behavior change at the host enforcement point
