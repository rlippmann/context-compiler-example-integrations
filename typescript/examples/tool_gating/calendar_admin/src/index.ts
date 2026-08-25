import {
  Engine,
  POLICY_PROHIBIT,
  POLICY_USE,
} from "@rlippmann/context-compiler";
import {
  decisionMessage,
  policyItems,
  snapshotState,
  type CompilerState
} from "./compiler-state.js";

declare const process: { argv: string[]; exitCode?: number };

export type CalendarToolCall = {
  toolName: string;
  calendarId: string;
  eventTitle: string;
};

export type ToolRegistrySnapshot = {
  availableTools: string[];
  hiddenTools: string[];
};

export type CalendarToolExecutionResult = {
  authorizationState: "allowed" | "blocked";
  toolVisible: boolean;
  executed: boolean;
  blockedReason: string | null;
  toolResult: string | null;
  registrySnapshot: ToolRegistrySnapshot;
  executionLog: string[];
};

export type CalendarToolTurnResult = {
  decisionKind: "error" | "update" | "no_directive";
  promptToUser: string | null;
  executionResult: CalendarToolExecutionResult;
};

export class CalendarAdminHost {
  public readonly executionLog: string[] = [];
  private readonly alwaysAvailableTools = ["calendar_view_events"];
  private readonly calendarAdminTools = ["calendar_admin_create_event"];

  public visibleTools(state: CompilerState): ToolRegistrySnapshot {
    const availableTools = [...this.alwaysAvailableTools];
    const hiddenTools = [...this.calendarAdminTools];

    if (calendarAdminToolsAreAllowed(state)) {
      availableTools.push(...this.calendarAdminTools);
      hiddenTools.length = 0;
    }

    return {
      availableTools,
      hiddenTools
    };
  }

  public executeCalendarAdminTool(toolCall: CalendarToolCall): string {
    this.executionLog.push(
      `${toolCall.toolName}:${toolCall.calendarId}:${toolCall.eventTitle}`
    );
    return `created event '${toolCall.eventTitle}' on calendar '${toolCall.calendarId}'`;
  }
}

export function calendarAdminToolsAreAllowed(state: CompilerState): boolean {
  const useItems = new Set(policyItems(state, POLICY_USE));
  const prohibitItems = new Set(policyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("calendar_admin")) {
    return false;
  }

  return useItems.has("calendar_admin");
}

export function executeCalendarAdminToolIfAllowed(
  toolCall: CalendarToolCall,
  state: CompilerState,
  host: CalendarAdminHost
): CalendarToolExecutionResult {
  const registrySnapshot = host.visibleTools(state);
  const toolVisible = registrySnapshot.availableTools.includes(toolCall.toolName);

  if (!toolVisible) {
    return {
      authorizationState: "blocked",
      toolVisible: false,
      executed: false,
      blockedReason: "calendar_admin state not authorized",
      toolResult: null,
      registrySnapshot,
      executionLog: [...host.executionLog]
    };
  }

  const toolResult = host.executeCalendarAdminTool(toolCall);
  return {
    authorizationState: "allowed",
    toolVisible: true,
    executed: true,
    blockedReason: null,
    toolResult,
    registrySnapshot,
    executionLog: [...host.executionLog]
  };
}

export function handleCalendarAdminTurn(
  engine: Engine,
  compilerInput: string,
  toolCall: CalendarToolCall,
  host: CalendarAdminHost
): CalendarToolTurnResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "error") {
    return {
      decisionKind: "error",
      promptToUser: decisionMessage(decision),
      executionResult: {
        authorizationState: "blocked",
        toolVisible: false,
        executed: false,
        blockedReason:
          "semantic error blocks exposing calendar admin tools",
        toolResult: null,
        registrySnapshot: host.visibleTools(snapshotState(engine)),
        executionLog: [...host.executionLog]
      }
    };
  }

  const authoritativeState = snapshotState(engine);

  return {
    decisionKind: decision.kind,
    promptToUser: decisionMessage(decision),
    executionResult: executeCalendarAdminToolIfAllowed(
      toolCall,
      authoritativeState,
      host
    )
  };
}

export function runExample(): CalendarToolExecutionResult {
  const engine = new Engine();
  engine.step("use calendar_admin");
  const host = new CalendarAdminHost();

  return executeCalendarAdminToolIfAllowed(
    {
      toolName: "calendar_admin_create_event",
      calendarId: "ops-admin",
      eventTitle: "Quarterly access review"
    },
    snapshotState(engine),
    host
  );
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: tool gating with calendar admin tools");
  console.log(JSON.stringify(result, null, 2));
}
