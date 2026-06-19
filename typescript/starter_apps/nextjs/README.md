# Next.js starter apps

The Next.js starter app now comes in two small variants:

- [basic](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/basic/README.md) - compiler-only baseline adapted from the last `nextjs-basic` example in `context-compiler-ts`
- [with_drafter](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/with_drafter/README.md) - optional directive-drafter layer before `engine.step(...)`

In both variants:

- `@rlippmann/context-compiler` remains the authority over saved state
- request construction is the enforcement point
- directive-drafter, when present, is optional acquisition help rather than the authority layer
