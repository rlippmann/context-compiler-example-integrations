import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { createEngine, type EngineState } from "@rlippmann/context-compiler";

import {
  CalendarAdminMcpHost,
  type McpToolCall,
  type McpToolDefinition
} from "./index.js";

export type SideEffectRecord = {
  toolName: string;
  calendarId: string;
  eventTitle: string;
  authorizationSource: "context_compiler_state";
};

export type LiveModelResult = {
  decisionKind: "clarify" | "update" | "passthrough" | null;
  promptToUser: string | null;
  exposedToolNames: string[];
  hiddenToolNames: string[];
  protectedToolExposed: boolean;
  selectedToolName: string | null;
  executed: boolean;
  blockedReason: string | null;
  toolResult: string | null;
  executionLog: string[];
  sideEffectPath: string;
  sideEffectCount: number;
};

export type SelectedToolCall = {
  name: string | null;
  arguments: Record<string, string>;
};

export type ModelToolSelector = (input: {
  userIntent: string;
  tools: OpenAiToolDefinition[];
}) => Promise<SelectedToolCall>;

type ChatCompletionRequestBody = {
  model: string;
  tool_choice: "auto";
  messages: Array<{ role: "system" | "user"; content: string }>;
  tools: OpenAiToolDefinition[];
  temperature?: number;
};

type OpenAiToolDefinition = {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: {
      type: "object";
      properties: Record<string, { type: "string"; description: string }>;
      required: string[];
      additionalProperties: false;
    };
  };
};

function buildOpenAiTools(exposedTools: McpToolDefinition[]): OpenAiToolDefinition[] {
  return exposedTools.flatMap((tool) => {
    if (tool.name === "calendar_view_events") {
      return [
        {
          type: "function",
          function: {
            name: tool.name,
            description: tool.description,
            parameters: {
              type: "object",
              properties: {
                calendar_id: {
                  type: "string",
                  description: "Calendar identifier to inspect."
                }
              },
              required: ["calendar_id"],
              additionalProperties: false
            }
          }
        }
      ];
    }

    if (tool.name === "calendar_admin_create_event") {
      return [
        {
          type: "function",
          function: {
            name: tool.name,
            description: tool.description,
            parameters: {
              type: "object",
              properties: {
                calendar_id: {
                  type: "string",
                  description: "Administrative calendar identifier."
                },
                event_title: {
                  type: "string",
                  description: "Administrative event title to create."
                }
              },
              required: ["calendar_id", "event_title"],
              additionalProperties: false
            }
          }
        }
      ];
    }

    return [];
  });
}

function sideEffectCount(artifactPath: string): number {
  if (!existsSync(artifactPath)) {
    return 0;
  }

  return readFileSync(artifactPath, "utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0).length;
}

function appendSideEffect(artifactPath: string, toolCall: McpToolCall): void {
  const record: SideEffectRecord = {
    toolName: toolCall.toolName,
    calendarId: toolCall.arguments.calendar_id ?? "",
    eventTitle: toolCall.arguments.event_title ?? "",
    authorizationSource: "context_compiler_state"
  };

  mkdirSync(dirname(artifactPath), { recursive: true });
  appendFileSync(artifactPath, `${JSON.stringify(record)}\n`, "utf8");
}

function normalizeToolArguments(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, String(item)])
  );
}

function extractSelectedToolCall(response: unknown): SelectedToolCall {
  if (!response || typeof response !== "object") {
    return { name: null, arguments: {} };
  }

  const choices = "choices" in response ? response.choices : null;
  if (!Array.isArray(choices) || choices.length === 0) {
    return { name: null, arguments: {} };
  }

  const firstChoice = choices[0];
  if (!firstChoice || typeof firstChoice !== "object" || !("message" in firstChoice)) {
    return { name: null, arguments: {} };
  }

  const message = firstChoice.message;
  if (!message || typeof message !== "object" || !("tool_calls" in message)) {
    return { name: null, arguments: {} };
  }

  const toolCalls = message.tool_calls;
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
    return { name: null, arguments: {} };
  }

  const firstToolCall = toolCalls[0];
  if (!firstToolCall || typeof firstToolCall !== "object" || !("function" in firstToolCall)) {
    return { name: null, arguments: {} };
  }

  const fn = firstToolCall.function;
  if (!fn || typeof fn !== "object" || !("name" in fn)) {
    return { name: null, arguments: {} };
  }

  const name = typeof fn.name === "string" ? fn.name : null;
  const rawArguments =
    "arguments" in fn && typeof fn.arguments === "string"
      ? fn.arguments
      : "{}";

  try {
    return {
      name,
      arguments: normalizeToolArguments(JSON.parse(rawArguments))
    };
  } catch {
    return { name, arguments: {} };
  }
}

export function resolveProviderConfig(): {
  apiKey: string;
  baseUrl: string;
  model: string;
} {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for live-model validation.");
  }

  return {
    apiKey,
    baseUrl: process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1",
    model: process.env.MODEL ?? "gpt-4o-mini"
  };
}

export function buildChatCompletionRequestBody(input: {
  model: string;
  userIntent: string;
  tools: OpenAiToolDefinition[];
}): ChatCompletionRequestBody {
  const body: ChatCompletionRequestBody = {
    model: input.model,
    tool_choice: "auto",
    messages: [
      {
        role: "system",
        content:
          "You are a careful assistant. Use a tool if one is available to complete the user's request. Do not invent unavailable tools."
      },
      { role: "user", content: input.userIntent }
    ],
    tools: input.tools
  };

  if (!isGpt5FamilyModel(input.model)) {
    body.temperature = 0;
  }

  return body;
}

export function isGpt5FamilyModel(model: string): boolean {
  return model === "gpt-5" || model.startsWith("gpt-5-");
}

async function callLiveModel(input: {
  userIntent: string;
  tools: OpenAiToolDefinition[];
}): Promise<SelectedToolCall> {
  const { apiKey, baseUrl, model } = resolveProviderConfig();
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify(
      buildChatCompletionRequestBody({
        model,
        userIntent: input.userIntent,
        tools: input.tools
      })
    )
  });

  if (!response.ok) {
    throw new Error(
      `Live-model request failed with status ${response.status}: ${await response.text()}`
    );
  }

  return extractSelectedToolCall(await response.json());
}

export async function runLiveModelTurn(input: {
  userIntent: string;
  authoritativeState?: EngineState;
  compilerInput?: string;
  artifactPath: string;
  modelToolSelector?: ModelToolSelector;
}): Promise<LiveModelResult> {
  const {
    userIntent,
    authoritativeState,
    compilerInput = "",
    artifactPath,
    modelToolSelector = callLiveModel
  } = input;

  const host = new CalendarAdminMcpHost();
  const engine = createEngine(authoritativeState ? { state: authoritativeState } : undefined);
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      exposedToolNames: host.exposedMcpTools(engine.state).tools.map((tool) => tool.name),
      hiddenToolNames: host.exposedMcpTools(engine.state).hiddenToolNames,
      protectedToolExposed: host
        .exposedMcpTools(engine.state)
        .tools.some((tool) => tool.name === "calendar_admin_create_event"),
      selectedToolName: null,
      executed: false,
      blockedReason: "clarification required before exposing calendar admin MCP tools",
      toolResult: null,
      executionLog: [...host.executionLog],
      sideEffectPath: artifactPath,
      sideEffectCount: sideEffectCount(artifactPath)
    };
  }

  const resolvedState = decision.state ?? engine.state;
  const exposedTools = host.exposedMcpTools(resolvedState);
  const selectedTool = await modelToolSelector({
    userIntent,
    tools: buildOpenAiTools(exposedTools.tools)
  });
  const protectedToolExposed = exposedTools.tools.some(
    (tool) => tool.name === "calendar_admin_create_event"
  );

  if (selectedTool.name !== "calendar_admin_create_event") {
    return {
      decisionKind: decision.kind,
      promptToUser: decision.prompt_to_user,
      exposedToolNames: exposedTools.tools.map((tool) => tool.name),
      hiddenToolNames: exposedTools.hiddenToolNames,
      protectedToolExposed,
      selectedToolName: selectedTool.name,
      executed: false,
      blockedReason: protectedToolExposed
        ? "model did not select protected admin tool"
        : "protected admin tool was not exposed",
      toolResult: null,
      executionLog: [...host.executionLog],
      sideEffectPath: artifactPath,
      sideEffectCount: sideEffectCount(artifactPath)
    };
  }

  const toolCall: McpToolCall = {
    toolName: selectedTool.name,
    arguments: selectedTool.arguments
  };
  const toolResult = host.executeMcpTool(toolCall);
  appendSideEffect(artifactPath, toolCall);

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    exposedToolNames: exposedTools.tools.map((tool) => tool.name),
    hiddenToolNames: exposedTools.hiddenToolNames,
    protectedToolExposed,
    selectedToolName: selectedTool.name,
    executed: true,
    blockedReason: null,
    toolResult,
    executionLog: [...host.executionLog],
    sideEffectPath: artifactPath,
    sideEffectCount: sideEffectCount(artifactPath)
  };
}
