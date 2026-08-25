import { Engine } from "@rlippmann/context-compiler";
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
  | { kind: "error"; promptToUser: string }
  | {
      kind: "continue";
      requestPayload: {
        systemPrompt: string;
        history: Array<{ role: "user" | "assistant"; content: string }>;
        userInput: string;
      };
    };

function stateToSystemPrompt(state: { premise: string | null; policies: Record<string, "use" | "prohibit"> }): string {
  const policies = Object.entries(state.policies)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([item, policy]) => `- ${policy === "use" ? "USE" : "PROHIBIT"}: ${item}`)
    .join("\n");

  return [
    "You are an assistant operating under compiled context.",
    "",
    "PREMISE:",
    state.premise ?? "(none)",
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

  const engine = new Engine();
  const savedCheckpoint = loadSessionState(sessionId);

  if (savedCheckpoint) {
    engine.import_json(savedCheckpoint);
  }

  const decision = engine.step(input);

  if (decision.kind === "error") {
    saveSessionState(sessionId, engine.export_json());
    const payload: ChatResponse = {
      kind: "error",
      promptToUser: decision.message
    };
    return Response.json(payload);
  }

  saveSessionState(sessionId, engine.export_json());

  const payload: ChatResponse = {
    kind: "continue",
    requestPayload: {
      systemPrompt: stateToSystemPrompt({ premise: engine.premise, policies: engine.policies }),
      history: minimalRecentContext(history),
      userInput: input
    }
  };

  return Response.json(payload);
}
