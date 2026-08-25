import http from "node:http";
import { Engine } from "@rlippmann/context-compiler";

type CompilerState = {
  premise: string | null;
  policies: Record<string, "use" | "prohibit">;
  version: 2;
};

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
  | { kind: "continue"; output: string; systemPrompt: string };

type ChatResult = {
  status: number;
  payload: ChatResponse | { error: string; details?: string };
};

const checkpointBySession = new Map<string, string>();
const HOST = "127.0.0.1";
const PORT = 8080;

function loadCheckpoint(sessionId: string): string | null {
  return checkpointBySession.get(sessionId) ?? null;
}

function saveCheckpoint(sessionId: string, checkpoint: string): void {
  checkpointBySession.set(sessionId, checkpoint);
}

function stateToSystemPrompt(state: CompilerState): string {
  const items = Object.entries(state.policies);
  const policies = items
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

export async function handleChatBody(body: ChatBody): Promise<ChatResult> {
  try {
    const { sessionId, input, history } = body;
    if (!sessionId || !input) {
      return { status: 400, payload: { error: "sessionId and input are required" } };
    }

    const engine = new Engine();
    const savedCheckpoint = loadCheckpoint(sessionId);

    if (savedCheckpoint) {
      engine.import_json(savedCheckpoint);
    }

    const decision = engine.step(input);

    if (decision.kind === "error") {
      saveCheckpoint(sessionId, engine.export_json());
      return {
        status: 200,
        payload: { kind: "error", promptToUser: decision.message } satisfies ChatResponse
      };
    }

    saveCheckpoint(sessionId, engine.export_json());

    return {
      status: 200,
      payload: {
        kind: "continue",
        output: [
          "Normal host workflow would continue here.",
          "This compiler-only variant returns the compiled prompt instead of calling a live model."
        ].join(" "),
        systemPrompt: [
          stateToSystemPrompt({ premise: engine.premise, policies: engine.policies, version: 2 }),
          "",
          "RECENT MESSAGES:",
          JSON.stringify(minimalRecentContext(history), null, 2),
          "",
          `RAW USER INPUT: ${input}`
        ].join("\n")
      } satisfies ChatResponse
    };
  } catch (error) {
    return { status: 500, payload: { error: "internal_error", details: String(error) } };
  }
}

export function createChatServer(): http.Server {
  return http.createServer(async (req, res) => {
    if (req.method !== "POST" || req.url !== "/chat") {
      sendJson(res, 404, { error: "not_found" });
      return;
    }

    const parsed = await parseJson(req);
    const result = await handleChatBody(parsed);
    sendJson(res, result.status, result.payload);
  });
}

if (import.meta.url === new URL(process.argv[1], "file://").href) {
  const server = createChatServer();
  server.listen(PORT, HOST, () => {
    console.log(`Node basic starter listening on http://${HOST}:${PORT}/chat`);
  });
}
