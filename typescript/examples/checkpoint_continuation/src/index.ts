import { Engine } from "@rlippmann/context-compiler";

import {
  decisionMessage,
  policyItems,
  snapshotState,
  type CompilerState
} from "./compiler-state.js";

declare const process: { argv: string[]; exitCode?: number };

export type Checkpoint = string;

export type BookingRecord = {
  bookingId: string;
  activeItinerary: string;
};

export type BookingChangeResult = {
  compilerInput: string;
  decisionKind: "error" | "update" | "no_directive";
  promptToUser: string | null;
  activeItinerary: string;
  hostAppliedChange: false;
};

export class CheckpointStore {
  private savedCheckpoint: Checkpoint | null = null;

  public save(checkpoint: Checkpoint): void {
    this.savedCheckpoint = checkpoint;
  }

  public load(): Checkpoint {
    if (this.savedCheckpoint === null) {
      throw new Error("no checkpoint saved");
    }

    return this.savedCheckpoint;
  }
}

export function selectItineraryFromState(state: CompilerState): string | null {
  return policyItems(state, "use")[0] ?? null;
}

function decisionKindName(
  decision: { kind: string }
): "error" | "update" | "no_directive" {
  if (
    decision.kind !== "error" &&
    decision.kind !== "update" &&
    decision.kind !== "no_directive"
  ) {
    throw new Error(`unexpected decision kind: ${decision.kind}`);
  }

  return decision.kind;
}

export function initiateItineraryChange(
  engine: Engine,
  currentItinerary: string,
  requestedItinerary: string
): BookingChangeResult {
  const compilerInput = `use ${requestedItinerary} instead of ${currentItinerary}`;
  const decision = engine.step(compilerInput);

  return {
    compilerInput,
    decisionKind: decisionKindName(decision),
    promptToUser: decisionMessage(decision),
    activeItinerary: selectItineraryFromState(snapshotState(engine)) ?? currentItinerary,
    hostAppliedChange: false
  };
}

export function restoreEngineFromCheckpoint(checkpoint: Checkpoint): Engine {
  const engine = new Engine();
  engine.import_json(checkpoint);
  return engine;
}

export function restoreEngineFromAuthoritativeStateOnly(checkpoint: Checkpoint): Engine {
  return restoreEngineFromCheckpoint(checkpoint);
}

export function runExample(): {
  initialResult: BookingChangeResult;
  restoredState: CompilerState;
  savedCheckpoint: Checkpoint;
} {
  const initialBooking: BookingRecord = {
    bookingId: "booking-100",
    activeItinerary: "boston_trip"
  };
  const firstEngine = new Engine();
  const checkpointStore = new CheckpointStore();

  const initialResult = initiateItineraryChange(
    firstEngine,
    initialBooking.activeItinerary,
    "chicago_trip"
  );
  checkpointStore.save(firstEngine.export_json());

  const restoredEngine = restoreEngineFromCheckpoint(checkpointStore.load());

  return {
    initialResult,
    restoredState: snapshotState(restoredEngine),
    savedCheckpoint: checkpointStore.load()
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: compiler state persistence with travel booking");
  console.log(JSON.stringify(result, null, 2));
}
