import http from "node:http";
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
import {
  PREPROCESS_OUTCOME_DIRECTIVE,
  parsePreprocessorOutput,
  preprocessHeuristic
} from "@rlippmann/context-compiler-directive-drafter";

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
  | { kind: "continue"; output: string; systemPrompt: string };

const checkpointBySession = new Map<string, string>();
const HOST = "127.0.0.1";
const PORT = 8080;

function loadCheckpoint(sessionId: string): string | null {
  return checkpointBySession.get(sessionId) ?? null;
}

function saveCheckpoint(sessionId: string, checkpoint: string): void {
  checkpointBySession.set(sessionId, checkpoint);
}

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

function resolveEngineInput(engine: ReturnType<typeof createEngine>, userInput: string): string {
  if (engine.hasPendingClarification()) {
    return userInput;
  }

  const heuristic = preprocessHeuristic(userInput);
  if (heuristic.outcome !== PREPROCESS_OUTCOME_DIRECTIVE || heuristic.directive === null) {
    return userInput;
  }

  const parsedDirective = parsePreprocessorOutput(heuristic.directive, { sourceInput: userInput });
  return parsedDirective ?? userInput;
}

async function parseJson(req: http.IncomingMessage): Promise<ChatBody> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.from(chunk));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8")) as ChatBody;
}

function sendJson(res: http.ServerResponse, status: number, payload: unknown): void {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body)
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  if (req.method !== "POST" || req.url !== "/chat") {
    sendJson(res, 404, { error: "not_found" });
    return;
  }

  try {
    const { sessionId, input, history } = await parseJson(req);
    if (!sessionId || !input) {
      sendJson(res, 400, { error: "sessionId and input are required" });
      return;
    }

    const engine = createEngine();
    const savedCheckpoint = loadCheckpoint(sessionId);

    if (savedCheckpoint) {
      engine.importCheckpointJson(savedCheckpoint);
    } else if (history?.length) {
      const replayMessages = history.filter(
        (message): message is { role: "user"; content: string } =>
          message.role === "user" && typeof message.content === "string"
      );
      const replay = engine.applyTranscript(replayMessages);

      if (replay.kind === "confirm") {
        saveCheckpoint(sessionId, engine.exportCheckpointJson());
        sendJson(res, 200, { kind: DECISION_CLARIFY, promptToUser: replay.prompt_to_user } satisfies ChatResponse);
        return;
      }

      saveCheckpoint(sessionId, engine.exportCheckpointJson());
    }

    const engineInput = resolveEngineInput(engine, input);
    const decision = engine.step(engineInput);

    if (isClarify(decision)) {
      saveCheckpoint(sessionId, engine.exportCheckpointJson());
      sendJson(
        res,
        200,
        { kind: DECISION_CLARIFY, promptToUser: getClarifyPrompt(decision) } satisfies ChatResponse
      );
      return;
    }

    saveCheckpoint(sessionId, engine.exportCheckpointJson());

    const usedReplay = !savedCheckpoint && !!history?.length;
    const payload: ChatResponse = {
      kind: "continue",
      output: [
        "Normal host workflow would continue here.",
        "This example returns the compiled prompt instead of calling a live model."
      ].join(" "),
      systemPrompt: [
        stateToSystemPrompt(engine.state),
        "",
        "RECENT MESSAGES:",
        JSON.stringify(usedReplay ? [] : minimalRecentContext(history), null, 2),
        "",
        `RAW USER INPUT: ${input}`
      ].join("\n")
    };

    sendJson(res, 200, payload);
  } catch (error) {
    sendJson(res, 500, { error: "internal_error", details: String(error) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Node starter listening on http://${HOST}:${PORT}/chat`);
});
