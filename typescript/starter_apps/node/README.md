# Node starter apps

Open this folder when you want a small runnable Node host instead of a generic
example alone.

This area teaches execution authorization first. It shows how a host preserves
saved state across requests and changes runtime behavior before any downstream
model or tool path would continue.

The Node starter app now comes in two small variants:

- [basic](basic/README.md) - compiler-only baseline adapted from the last `node-basic` example in `context-compiler-ts`
- [with_drafter](with_drafter/README.md) - optional directive-drafter layer before `engine.step(...)`

Open `basic` first if you want the smallest baseline.

Open `with_drafter` when you want to compare that baseline with an optional
acquisition layer that still leaves saved-state authority with the compiler.

In both variants:

- `@rlippmann/context-compiler` remains the authority over saved state
- runtime behavior changes stay observable even if the model is replaced by a stub
- checkpoint persistence preserves saved state and pending `clarify` / `confirm` flows
