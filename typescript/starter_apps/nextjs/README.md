# Next.js starter apps

Open this folder when you want a minimal App Router host around the examples
instead of a generic example alone.

This area teaches request construction first. It shows how a host restores
saved state, builds a request payload from that state, and makes the runtime
effect visible before any live model call.

The Next.js starter app now comes in two small variants:

- [basic](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/basic/README.md) - compiler-only baseline adapted from the last `nextjs-basic` example in `context-compiler-ts`
- [with_drafter](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/with_drafter/README.md) - optional directive-drafter layer before `engine.step(...)`

Open `basic` first if you want the smallest baseline.

Open `with_drafter` when you want to compare that baseline with an optional
acquisition layer that still leaves saved-state authority with the compiler.

In both variants:

- `@rlippmann/context-compiler` remains the authority over saved state
- request construction is the enforcement point
- directive-drafter, when present, is optional acquisition help rather than the authority layer
