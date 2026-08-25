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

export type BookingChangeRuntimeResult = {
  compilerInput: string;
  decisionKind: "error" | "update" | "no_directive";
  promptToUser: string | null;
  checkpointPending: boolean;
  activeItinerary: string;
  hostAppliedChange: boolean;
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

export class BookingHost {
  public readonly appliedChanges: string[] = [];

  public constructor(public readonly booking: BookingRecord) {}

  public applySelectedItinerary(state: CompilerState): boolean {
    const selectedItinerary = selectItineraryFromState(state);
    if (selectedItinerary === null) {
      return false;
    }

    this.booking.activeItinerary = selectedItinerary;
    this.appliedChanges.push(selectedItinerary);
    return true;
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
): BookingChangeRuntimeResult {
  const compilerInput = `use ${requestedItinerary} instead of ${currentItinerary}`;
  const decision = engine.step(compilerInput);

  return {
    compilerInput,
    decisionKind: decisionKindName(decision),
    promptToUser: decisionMessage(decision),
    checkpointPending: false,
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

export function continueItineraryChange(
  engine: Engine,
  host: BookingHost,
  userInput: string
): BookingChangeRuntimeResult {
  const decision = engine.step(userInput);
  const hostAppliedChange =
    decisionKindName(decision) === "update"
      ? host.applySelectedItinerary(snapshotState(engine))
      : false;

  return {
    compilerInput: userInput,
    decisionKind: decisionKindName(decision),
    promptToUser: decisionMessage(decision),
    checkpointPending: false,
    activeItinerary: host.booking.activeItinerary,
    hostAppliedChange
  };
}

export function runExample(): {
  pendingResult: BookingChangeRuntimeResult;
  confirmedResult: BookingChangeRuntimeResult;
  savedCheckpoint: Checkpoint;
} {
  const initialBooking: BookingRecord = {
    bookingId: "booking-100",
    activeItinerary: "boston_trip"
  };
  const firstHost = new BookingHost({ ...initialBooking });
  const firstEngine = new Engine();
  const checkpointStore = new CheckpointStore();

  const pendingResult = initiateItineraryChange(
    firstEngine,
    firstHost.booking.activeItinerary,
    "chicago_trip"
  );
  checkpointStore.save(firstEngine.export_json());

  const resumedEngine = restoreEngineFromCheckpoint(checkpointStore.load());
  const resumedHost = new BookingHost({ ...firstHost.booking });
  const confirmedResult = continueItineraryChange(resumedEngine, resumedHost, "yes");

  return {
    pendingResult,
    confirmedResult,
    savedCheckpoint: checkpointStore.load()
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: checkpoint continuation with travel booking");
  console.log(JSON.stringify(result, null, 2));
}
