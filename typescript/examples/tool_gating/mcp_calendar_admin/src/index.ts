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
  decisionKind: "error" | "update" | "no_directive";
  promptToUser: string | null;
  executionResult: McpToolExecutionResult;
};

export type McpDecisionResult = {
  decisionKind: "error" | "update" | "no_directive";
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

  public exposedMcpTools(state: CompilerState): ExposedMcpTools {
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

export function calendarAdminMcpToolsAreAllowed(state: CompilerState): boolean {
  const useItems = new Set(policyItems(state, POLICY_USE));
  const prohibitItems = new Set(policyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("calendar_admin")) {
    return false;
  }

  return useItems.has("calendar_admin");
}

export function executeMcpToolIfAllowed(
  toolCall: McpToolCall,
  state: CompilerState,
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
  engine: Engine,
  compilerInput: string,
  toolCall: McpToolCall,
  host: CalendarAdminMcpHost
): McpToolTurnResult {
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
          "clarification required before exposing calendar admin MCP tools",
        toolResult: null,
        exposedTools: host.exposedMcpTools(snapshotState(engine)),
        executionLog: [...host.executionLog]
      }
    };
  }

  const authoritativeState = snapshotState(engine);

  return {
    decisionKind: decision.kind,
    promptToUser: decisionMessage(decision),
    executionResult: executeMcpToolIfAllowed(toolCall, authoritativeState, host)
  };
}

export function describeExposedMcpTools(
  engine: Engine,
  compilerInput: string,
  host: CalendarAdminMcpHost
): McpDecisionResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "error") {
    return {
      decisionKind: "error",
      promptToUser: decisionMessage(decision),
      exposedTools: host.exposedMcpTools(snapshotState(engine))
    };
  }

  const authoritativeState = snapshotState(engine);

  return {
    decisionKind: decision.kind,
    promptToUser: decisionMessage(decision),
    exposedTools: host.exposedMcpTools(authoritativeState)
  };
}

export function runExample(): McpToolExecutionResult {
  const engine = new Engine();
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
  console.log("integration example: MCP tool gating with calendar admin tools");
  console.log(JSON.stringify(result, null, 2));
}
