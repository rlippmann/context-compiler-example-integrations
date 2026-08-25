import { Engine } from "@rlippmann/context-compiler";

export type CompilerState = {
  premise: string | null;
  policies: Record<string, "use" | "prohibit">;
  version: 2;
};

export function snapshotState(engine: Engine): CompilerState {
  return { premise: engine.premise, policies: engine.policies, version: 2 };
}

export function policyItems(state: CompilerState, policy?: "use" | "prohibit"): string[] {
  return Object.entries(state.policies)
    .filter(([, value]) => policy === undefined || value === policy)
    .map(([item]) => item)
    .sort();
}

export function premiseValue(state: CompilerState): string | null {
  return state.premise;
}

export function engineFromState(state: CompilerState): Engine {
  const engine = new Engine();
  engine.import_json(JSON.stringify(state));
  return engine;
}
