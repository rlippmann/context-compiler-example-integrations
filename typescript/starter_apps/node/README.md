# Node starter apps

The Node starter app now comes in two small variants:

- [basic](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/basic/README.md) - compiler-only baseline adapted from the last `node-basic` example in `context-compiler-ts`
- [with_drafter](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/node/with_drafter/README.md) - optional directive-drafter layer before `engine.step(...)`

In both variants:

- `@rlippmann/context-compiler` remains the authority over saved state
- runtime behavior changes stay observable even if the model is replaced by a stub
- checkpoint persistence preserves saved state and pending `clarify` / `confirm` flows
