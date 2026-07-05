import { createOpenAI } from "@ai-sdk/openai";
import { generateObject } from "ai";
import {
  createEngine,
  type EngineState
} from "@rlippmann/context-compiler";

import {
  buildGenerateObjectRequest,
  type StructuredSchemaName
} from "./index.js";

export type LiveProviderConfig = {
  apiKey: string;
  model: string;
};

export type LiveGenerateObjectResult =
  | {
      called: false;
      schemaName: null;
      object: null;
    }
  | {
      called: true;
      schemaName: StructuredSchemaName;
      object: unknown;
    };

export function resolveLiveProviderConfig(): LiveProviderConfig {
  const apiKey = process.env.OPENAI_API_KEY;

  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for live-model validation.");
  }

  return {
    apiKey,
    model: process.env.MODEL ?? "gpt-4o-mini"
  };
}

export async function runLiveGenerateObject(input: {
  prompt: string;
  authoritativeState?: EngineState;
  compilerInput?: string;
}): Promise<LiveGenerateObjectResult> {
  const engine = createEngine(
    input.authoritativeState ? { state: input.authoritativeState } : undefined
  );

  if (input.compilerInput) {
    engine.step(input.compilerInput);
  }

  const request = buildGenerateObjectRequest(engine.state, input.prompt);

  if (request === null) {
    return {
      called: false,
      schemaName: null,
      object: null
    };
  }

  const { apiKey, model } = resolveLiveProviderConfig();
  const openai = createOpenAI({ apiKey });
  const result = await generateObject({
    model: openai(model),
    prompt: request.prompt,
    schema: request.schema.schema
  });

  return {
    called: true,
    schemaName: request.schemaName,
    object: result.object
  };
}
