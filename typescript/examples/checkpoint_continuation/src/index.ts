import {
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type Engine,
  type EngineCheckpoint,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export type Checkpoint = EngineCheckpoint;

export type BookingRecord = {
  bookingId: string;
  activeItinerary: string;
};

export type BookingChangeRuntimeResult = {
  compilerInput: string;
  decisionKind: "clarify" | "update" | "passthrough";
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

  public applySelectedItinerary(state: EngineState): boolean {
    const selectedItinerary = selectItineraryFromState(state);
    if (selectedItinerary === null) {
      return false;
    }

    this.booking.activeItinerary = selectedItinerary;
    this.appliedChanges.push(selectedItinerary);
    return true;
  }
}

export function selectItineraryFromState(state: EngineState): string | null {
  const useItems = getPolicyItems(state, POLICY_USE);
  if (useItems.length === 0) {
    return null;
  }

  return useItems[0] ?? null;
}

function decisionKindName(decision: { kind: string }): "clarify" | "update" | "passthrough" {
  if (
    decision.kind !== "clarify" &&
    decision.kind !== "update" &&
    decision.kind !== "passthrough"
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
    promptToUser: decision.prompt_to_user,
    checkpointPending: engine.hasPendingClarification(),
    activeItinerary: selectItineraryFromState(engine.state) ?? currentItinerary,
    hostAppliedChange: false
  };
}

export function restoreEngineFromCheckpoint(checkpoint: Checkpoint): Engine {
  const engine = createEngine();
  engine.importCheckpoint(checkpoint);
  return engine;
}

export function restoreEngineFromAuthoritativeStateOnly(checkpoint: Checkpoint): Engine {
  return createEngine({ state: checkpoint.authoritative_state });
}

export function continueItineraryChange(
  engine: Engine,
  host: BookingHost,
  userInput: string
): BookingChangeRuntimeResult {
  const decision = engine.step(userInput);
  let hostAppliedChange = false;

  if (decisionKindName(decision) === "update") {
    hostAppliedChange = host.applySelectedItinerary(engine.state);
  }

  return {
    compilerInput: userInput,
    decisionKind: decisionKindName(decision),
    promptToUser: decision.prompt_to_user,
    checkpointPending: engine.hasPendingClarification(),
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
  const firstEngine = createEngine();
  const checkpointStore = new CheckpointStore();

  const pendingResult = initiateItineraryChange(
    firstEngine,
    firstHost.booking.activeItinerary,
    "chicago_trip"
  );
  checkpointStore.save(firstEngine.exportCheckpoint());

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
