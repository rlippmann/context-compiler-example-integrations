import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export type McpToolDefinition = {
  name: string;
  title: string;
  description: string;
};

export type McpToolCall = {
  toolName: string;
  arguments: Record<string, string>;
};

export type ExposedMcpTools = {
  tools: McpToolDefinition[];
  hiddenToolNames: string[];
};

export type McpToolExecutionResult = {
  authorizationState: "allowed" | "blocked";
  toolVisible: boolean;
  executed: boolean;
  blockedReason: string | null;
  toolResult: string | null;
  exposedTools: ExposedMcpTools;
  executionLog: string[];
};

export type McpToolTurnResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  executionResult: McpToolExecutionResult;
};

export type McpDecisionResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  exposedTools: ExposedMcpTools;
};

export class CalendarAdminMcpHost {
  public readonly executionLog: string[] = [];
  private readonly alwaysAvailableTools: McpToolDefinition[] = [
    {
      name: "calendar_view_events",
      title: "View calendar events",
      description: "List visible events from a calendar."
    }
  ];
  private readonly calendarAdminTools: McpToolDefinition[] = [
    {
      name: "calendar_admin_create_event",
      title: "Create calendar event",
      description: "Create an administrative event on a calendar."
    }
  ];

  public exposedMcpTools(state: EngineState): ExposedMcpTools {
    const tools = [...this.alwaysAvailableTools];
    let hiddenToolNames = this.calendarAdminTools.map((tool) => tool.name);

    if (calendarAdminMcpToolsAreAllowed(state)) {
      tools.push(...this.calendarAdminTools);
      hiddenToolNames = [];
    }

    return {
      tools,
      hiddenToolNames
    };
  }

  public executeMcpTool(toolCall: McpToolCall): string {
    const calendarId = toolCall.arguments.calendar_id;
    const eventTitle = toolCall.arguments.event_title;
    this.executionLog.push(`${toolCall.toolName}:${calendarId}:${eventTitle}`);
    return `created event '${eventTitle}' on calendar '${calendarId}'`;
  }
}

export function calendarAdminMcpToolsAreAllowed(state: EngineState): boolean {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("calendar_admin")) {
    return false;
  }

  return useItems.has("calendar_admin");
}

export function executeMcpToolIfAllowed(
  toolCall: McpToolCall,
  state: EngineState,
  host: CalendarAdminMcpHost
): McpToolExecutionResult {
  const exposedTools = host.exposedMcpTools(state);
  const toolVisible = exposedTools.tools.some((tool) => tool.name === toolCall.toolName);

  if (!toolVisible) {
    return {
      authorizationState: "blocked",
      toolVisible: false,
      executed: false,
      blockedReason: "calendar_admin state not authorized",
      toolResult: null,
      exposedTools,
      executionLog: [...host.executionLog]
    };
  }

  const toolResult = host.executeMcpTool(toolCall);
  return {
    authorizationState: "allowed",
    toolVisible: true,
    executed: true,
    blockedReason: null,
    toolResult,
    exposedTools,
    executionLog: [...host.executionLog]
  };
}

export function handleMcpToolTurn(
  engine: ReturnType<typeof createEngine>,
  compilerInput: string,
  toolCall: McpToolCall,
  host: CalendarAdminMcpHost
): McpToolTurnResult {
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
          "clarification required before exposing calendar admin MCP tools",
        toolResult: null,
        exposedTools: host.exposedMcpTools(engine.state),
        executionLog: [...host.executionLog]
      }
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    executionResult: executeMcpToolIfAllowed(toolCall, authoritativeState, host)
  };
}

export function describeExposedMcpTools(
  engine: ReturnType<typeof createEngine>,
  compilerInput: string,
  host: CalendarAdminMcpHost
): McpDecisionResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      exposedTools: host.exposedMcpTools(engine.state)
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    exposedTools: host.exposedMcpTools(authoritativeState)
  };
}

export function runExample(): McpToolExecutionResult {
  const engine = createEngine();
  engine.step("use calendar_admin");
  const host = new CalendarAdminMcpHost();

  return executeMcpToolIfAllowed(
    {
      toolName: "calendar_admin_create_event",
      arguments: {
        calendar_id: "ops-admin",
        event_title: "Quarterly access review"
      }
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
  console.log("integration example: MCP tool gating with calendar admin tools");
  console.log(JSON.stringify(result, null, 2));
}
