import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";

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
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  executionResult: CalendarToolExecutionResult;
};

export class CalendarAdminHost {
  public readonly executionLog: string[] = [];
  private readonly alwaysAvailableTools = ["calendar_view_events"];
  private readonly calendarAdminTools = ["calendar_admin_create_event"];

  public visibleTools(state: EngineState): ToolRegistrySnapshot {
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

export function calendarAdminToolsAreAllowed(state: EngineState): boolean {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("calendar_admin")) {
    return false;
  }

  return useItems.has("calendar_admin");
}

export function executeCalendarAdminToolIfAllowed(
  toolCall: CalendarToolCall,
  state: EngineState,
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
  engine: ReturnType<typeof createEngine>,
  compilerInput: string,
  toolCall: CalendarToolCall,
  host: CalendarAdminHost
): CalendarToolTurnResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      executionResult: {
        authorizationState: "blocked",
        toolVisible: false,
        executed: false,
        blockedReason:
          "clarification required before exposing calendar admin tools",
        toolResult: null,
        registrySnapshot: host.visibleTools(engine.state),
        executionLog: [...host.executionLog]
      }
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    executionResult: executeCalendarAdminToolIfAllowed(
      toolCall,
      authoritativeState,
      host
    )
  };
}

export function runExample(): CalendarToolExecutionResult {
  const engine = createEngine();
  engine.step("use calendar_admin");
  const host = new CalendarAdminHost();

  return executeCalendarAdminToolIfAllowed(
    {
      toolName: "calendar_admin_create_event",
      calendarId: "ops-admin",
      eventTitle: "Quarterly access review"
    },
    engine.state,
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
