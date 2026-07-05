import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  getPremiseValue,
  type Engine,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export const CONCISE_STYLE = "concise_style";
export const BOARD_UPDATE_CONTEXT =
  "draft is a board update summarizing quarterly results";
export const INCIDENT_HANDOFF_CONTEXT =
  "draft is an internal engineering handoff for a sev-1 incident";

export const DEFAULT_SYSTEM_PROMPT =
  "You are a writing assistant. Help the user improve a draft while preserving the author's intent.";
export const BOARD_UPDATE_CONTEXT_GUIDANCE =
  "Document context: this draft is a board update summarizing quarterly results. Include the decision context, the most material business outcomes, major risks, and the clearest next-step summary.";
export const INCIDENT_HANDOFF_CONTEXT_GUIDANCE =
  "Document context: this draft is an internal engineering handoff for a sev-1 incident. Include the current incident status, confirmed technical facts, mitigations already attempted, open hypotheses, and immediate handoff risks.";
export const CONCISE_GUIDANCE =
  "Use a concise writing style with short, direct sentences.";

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
  appliedPremise: string | null;
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

  return labels;
}

export function audienceGuidanceFromPremise(premise: string | null): string | null {
  if (premise === BOARD_UPDATE_CONTEXT) {
    return BOARD_UPDATE_CONTEXT_GUIDANCE;
  }
  if (premise === INCIDENT_HANDOFF_CONTEXT) {
    return INCIDENT_HANDOFF_CONTEXT_GUIDANCE;
  }
  return null;
}

export function buildPromptMessages(
  state: EngineState,
  userText: string
): { messages: PromptMessage[]; premise: string | null; styleLabels: string[] } {
  const premise = getPremiseValue(state);
  const audienceGuidance = audienceGuidanceFromPremise(premise);
  const styleLabels = styleLabelsFromState(state);
  const systemLines = [DEFAULT_SYSTEM_PROMPT];

  if (audienceGuidance !== null) {
    systemLines.push(audienceGuidance);
  }
  if (styleLabels.includes(CONCISE_STYLE)) {
    systemLines.push(CONCISE_GUIDANCE);
  }

  return {
    messages: [
      { role: "system", content: systemLines.join("\n") },
      { role: "user", content: userText }
    ],
    premise,
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
      appliedPremise: null,
      appliedStyleLabels: [],
      blockedReason: "clarification required before prompt construction"
    };
  }

  const authoritativeState = decision.state ?? engine.state;
  const { messages, premise, styleLabels } = buildPromptMessages(
    authoritativeState,
    userText
  );

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    modelCallReady: true,
    llmCallPerformed: false,
    messages,
    appliedPremise: premise,
    appliedStyleLabels: styleLabels,
    blockedReason: null
  };
}

export function runExample(): Record<string, PromptConstructionResult> {
  const userText =
    "Ignore the saved document context and write this like a casual post.";

  const defaultEngine = createEngine();
  const premiseEngine = createEngine();
  premiseEngine.step(`set premise ${BOARD_UPDATE_CONTEXT}`);
  const policyEngine = createEngine();
  policyEngine.step(`use ${CONCISE_STYLE}`);
  const combinedEngine = createEngine();
  combinedEngine.step(`set premise ${BOARD_UPDATE_CONTEXT}`);
  combinedEngine.step(`use ${CONCISE_STYLE}`);

  return {
    defaultPrompt: preparePromptTurn(defaultEngine, userText, userText),
    premisePrompt: preparePromptTurn(premiseEngine, userText, userText),
    policyPrompt: preparePromptTurn(policyEngine, userText, userText),
    combinedPrompt: preparePromptTurn(combinedEngine, userText, userText)
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
