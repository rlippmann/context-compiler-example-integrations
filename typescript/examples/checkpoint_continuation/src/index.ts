import { Engine } from "@rlippmann/context-compiler";

import {
  decisionMessage,
  policyItems,
  snapshotState,
  type CompilerState
} from "./compiler-state.js";

declare const process: { argv: string[]; exitCode?: number };

export type PersistedState = string;

export type BookingRecord = {
  bookingId: string;
  activeItinerary: string;
};

export type BookingChangeRuntimeResult = {
  compilerInput: string;
  decisionKind: "error" | "update" | "no_directive";
  messageToUser: string | null;
  persistedStateJson: PersistedState;
  selectedItinerary: string | null;
  hostAppliedChange: boolean;
  activeItinerary: string;
};

export class EnginePersistenceStore {
  private savedStateJson: PersistedState | null = null;

  public save(stateJson: PersistedState): void {
    this.savedStateJson = stateJson;
  }

  public load(): PersistedState {
    if (this.savedStateJson === null) {
      throw new Error("no saved state");
    }

    return this.savedStateJson;
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

export function persistItinerarySelection(
  engine: Engine,
  requestedItinerary: string
): BookingChangeRuntimeResult {
  const compilerInput = `use ${requestedItinerary}`;
  const decision = engine.step(compilerInput);
  const persistedStateJson = engine.export_json();
  const state = snapshotState(engine);
  const selectedItinerary = selectItineraryFromState(state);

  return {
    compilerInput,
    decisionKind: decisionKindName(decision),
    messageToUser: decisionMessage(decision),
    persistedStateJson,
    selectedItinerary,
    hostAppliedChange: false,
    activeItinerary: selectedItinerary ?? "boston_trip"
  };
}

export function restoreEngineFromPersistedState(stateJson: PersistedState): Engine {
  const engine = new Engine();
  engine.import_json(stateJson);
  return engine;
}

export function applyRestoredItinerary(
  engine: Engine,
  host: BookingHost
): BookingChangeRuntimeResult {
  const state = snapshotState(engine);
  const hostAppliedChange = host.applySelectedItinerary(state);
  const selectedItinerary = selectItineraryFromState(state);

  return {
    compilerInput: "",
    decisionKind: hostAppliedChange ? "update" : "no_directive",
    messageToUser: null,
    persistedStateJson: engine.export_json(),
    selectedItinerary,
    hostAppliedChange,
    activeItinerary: host.booking.activeItinerary
  };
}

export function runExample(): {
  persistedResult: BookingChangeRuntimeResult;
  appliedResult: BookingChangeRuntimeResult;
  savedStateJson: PersistedState;
} {
  const initialBooking: BookingRecord = {
    bookingId: "booking-100",
    activeItinerary: "boston_trip"
  };
  const firstEngine = new Engine();
  const persistenceStore = new EnginePersistenceStore();

  const persistedResult = persistItinerarySelection(firstEngine, "chicago_trip");
  persistenceStore.save(persistedResult.persistedStateJson);

  const restoredEngine = restoreEngineFromPersistedState(persistenceStore.load());
  const restoredHost = new BookingHost({ ...initialBooking });
  const appliedResult = applyRestoredItinerary(restoredEngine, restoredHost);

  return {
    persistedResult,
    appliedResult,
    savedStateJson: persistenceStore.load()
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
