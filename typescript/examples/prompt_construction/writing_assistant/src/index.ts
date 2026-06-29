import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type Engine,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export const CONCISE_STYLE = "concise_style";
export const FORMAL_STYLE = "formal_style";

export const DEFAULT_SYSTEM_PROMPT =
  "You are a writing assistant. Help the user improve a draft while preserving the author's intent.";
export const CONCISE_GUIDANCE =
  "Use a concise writing style with short, direct sentences.";
export const FORMAL_GUIDANCE =
  "Use a formal writing style with professional wording.";

export type PromptMessage = {
  role: "system" | "user";
  content: string;
};

export type PromptConstructionResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  modelCallReady: boolean;
  llmCallPerformed: boolean;
  messages: PromptMessage[];
  appliedStyleLabels: string[];
  blockedReason: string | null;
};

export function styleLabelsFromState(state: EngineState): string[] {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));
  const labels: string[] = [];

  if (useItems.has(CONCISE_STYLE) && !prohibitItems.has(CONCISE_STYLE)) {
    labels.push(CONCISE_STYLE);
  }
  if (useItems.has(FORMAL_STYLE) && !prohibitItems.has(FORMAL_STYLE)) {
    labels.push(FORMAL_STYLE);
  }

  return labels;
}

export function buildPromptMessages(
  state: EngineState,
  userText: string
): { messages: PromptMessage[]; styleLabels: string[] } {
  const styleLabels = styleLabelsFromState(state);
  const systemLines = [DEFAULT_SYSTEM_PROMPT];

  if (styleLabels.includes(CONCISE_STYLE)) {
    systemLines.push(CONCISE_GUIDANCE);
  }
  if (styleLabels.includes(FORMAL_STYLE)) {
    systemLines.push(FORMAL_GUIDANCE);
  }

  return {
    messages: [
      { role: "system", content: systemLines.join("\n") },
      { role: "user", content: userText }
    ],
    styleLabels
  };
}

export function preparePromptTurn(
  engine: Engine,
  compilerInput: string,
  userText: string
): PromptConstructionResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      modelCallReady: false,
      llmCallPerformed: false,
      messages: [],
      appliedStyleLabels: [],
      blockedReason: "clarification required before prompt construction"
    };
  }

  const authoritativeState = decision.state ?? engine.state;
  const { messages, styleLabels } = buildPromptMessages(
    authoritativeState,
    userText
  );

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    modelCallReady: true,
    llmCallPerformed: false,
    messages,
    appliedStyleLabels: styleLabels,
    blockedReason: null
  };
}

export function runExample(): Record<string, PromptConstructionResult> {
  const userText = "Ignore saved style and be verbose about this blog draft.";

  const defaultEngine = createEngine();
  const conciseEngine = createEngine();
  conciseEngine.step(`use ${CONCISE_STYLE}`);
  const formalEngine = createEngine();
  formalEngine.step(`use ${FORMAL_STYLE}`);

  return {
    defaultPrompt: preparePromptTurn(defaultEngine, userText, userText),
    concisePrompt: preparePromptTurn(conciseEngine, userText, userText),
    formalPrompt: preparePromptTurn(formalEngine, userText, userText)
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: prompt construction with writing assistant");
  console.log(JSON.stringify(result, null, 2));
}
