import {
  DECISION_CLARIFY,
  POLICY_USE,
  createEngine,
  getClarifyPrompt,
  getPolicyItems,
  getPremiseValue,
  isClarify,
  type EngineState
} from "@rlippmann/context-compiler";
import { loadSessionState, saveSessionState } from "../../../lib/context-sessions.ts";

type ChatMessage = {
  role: string;
  content: unknown;
};

type ChatBody = {
  sessionId: string;
  input: string;
  history?: ChatMessage[];
};

type ChatResponse =
  | { kind: typeof DECISION_CLARIFY; promptToUser: string | null }
  | {
      kind: "continue";
      requestPayload: {
        systemPrompt: string;
        history: Array<{ role: "user" | "assistant"; content: string }>;
        userInput: string;
      };
    };

function stateToSystemPrompt(state: EngineState): string {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const policies = getPolicyItems(state)
    .map((item) => `- ${useItems.has(item) ? "USE" : "PROHIBIT"}: ${item}`)
    .join("\n");

  return [
    "You are an assistant operating under compiled context.",
    "",
    "PREMISE:",
    getPremiseValue(state) ?? "(none)",
    "",
    "POLICIES:",
    policies || "(none)",
    "",
    "Follow these constraints strictly."
  ].join("\n");
}

function minimalRecentContext(history: ChatMessage[] | undefined) {
  if (!history?.length) {
    return [];
  }

  return history
    .filter(
      (message): message is { role: "user" | "assistant"; content: string } =>
        (message.role === "user" || message.role === "assistant") && typeof message.content === "string"
    )
    .slice(-2)
    .map((message) => ({ role: message.role, content: message.content }));
}

export async function POST(req: Request): Promise<Response> {
  const { sessionId, input, history } = (await req.json()) as ChatBody;

  if (!sessionId || !input) {
    return Response.json({ error: "sessionId and input are required" }, { status: 400 });
  }

  const engine = createEngine();
  const savedCheckpoint = loadSessionState(sessionId);

  if (savedCheckpoint) {
    engine.importCheckpointJson(savedCheckpoint);
  } else if (history?.length) {
    const replayMessages = history.filter(
      (message): message is { role: "user"; content: string } =>
        message.role === "user" && typeof message.content === "string"
    );
    const replay = engine.applyTranscript(replayMessages);

    if (replay.kind === "confirm") {
      saveSessionState(sessionId, engine.exportCheckpointJson());
      const payload: ChatResponse = {
        kind: DECISION_CLARIFY,
        promptToUser: replay.prompt_to_user
      };
      return Response.json(payload);
    }

    saveSessionState(sessionId, engine.exportCheckpointJson());
  }

  const decision = engine.step(input);

  if (isClarify(decision)) {
    saveSessionState(sessionId, engine.exportCheckpointJson());
    const payload: ChatResponse = {
      kind: DECISION_CLARIFY,
      promptToUser: getClarifyPrompt(decision)
    };
    return Response.json(payload);
  }

  saveSessionState(sessionId, engine.exportCheckpointJson());

  const usedReplay = !savedCheckpoint && !!history?.length;
  const payload: ChatResponse = {
    kind: "continue",
    requestPayload: {
      systemPrompt: stateToSystemPrompt(engine.state),
      history: usedReplay ? [] : minimalRecentContext(history),
      userInput: input
    }
  };

  return Response.json(payload);
}
