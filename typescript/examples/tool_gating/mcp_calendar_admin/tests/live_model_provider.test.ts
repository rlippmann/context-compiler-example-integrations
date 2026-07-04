import assert from "node:assert/strict";
import test from "node:test";

import {
  buildChatCompletionRequestBody,
  resolveProviderConfig
} from "../src/live_model.js";

test("resolveProviderConfig preserves exact model ids for OpenAI-compatible requests", () => {
  const previousModel = process.env.MODEL;
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousBaseUrl = process.env.OPENAI_BASE_URL;

  process.env.MODEL = "qwen2.5:1.5b-instruct";
  process.env.OPENAI_API_KEY = "ollama";
  process.env.OPENAI_BASE_URL = "http://127.0.0.1:11434/v1";

  try {
    const config = resolveProviderConfig();

    assert.equal(config.model, "qwen2.5:1.5b-instruct");
    assert.equal(config.apiKey, "ollama");
    assert.equal(config.baseUrl, "http://127.0.0.1:11434/v1");
  } finally {
    restoreEnv("MODEL", previousModel);
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("OPENAI_BASE_URL", previousBaseUrl);
  }
});

test("resolveProviderConfig preserves exact model ids for OpenAI", () => {
  const previousModel = process.env.MODEL;
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousBaseUrl = process.env.OPENAI_BASE_URL;

  process.env.MODEL = "gpt-4o-mini";
  process.env.OPENAI_API_KEY = "test-key";
  delete process.env.OPENAI_BASE_URL;

  try {
    const config = resolveProviderConfig();

    assert.equal(config.model, "gpt-4o-mini");
    assert.equal(config.apiKey, "test-key");
    assert.equal(config.baseUrl, "https://api.openai.com/v1");
  } finally {
    restoreEnv("MODEL", previousModel);
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("OPENAI_BASE_URL", previousBaseUrl);
  }
});

test("resolveProviderConfig uses OpenAI default model when MODEL is unset", () => {
  const previousModel = process.env.MODEL;
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousBaseUrl = process.env.OPENAI_BASE_URL;

  delete process.env.MODEL;
  process.env.OPENAI_API_KEY = "test-key";
  delete process.env.OPENAI_BASE_URL;

  try {
    const config = resolveProviderConfig();

    assert.equal(config.model, "gpt-4o-mini");
    assert.equal(config.baseUrl, "https://api.openai.com/v1");
  } finally {
    restoreEnv("MODEL", previousModel);
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("OPENAI_BASE_URL", previousBaseUrl);
  }
});

test("resolveProviderConfig requires OPENAI_API_KEY for direct HTTP calls", () => {
  const previousModel = process.env.MODEL;
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousBaseUrl = process.env.OPENAI_BASE_URL;

  process.env.MODEL = "gpt-4o-mini";
  delete process.env.OPENAI_API_KEY;
  delete process.env.OPENAI_BASE_URL;

  try {
    assert.throws(
      () => resolveProviderConfig(),
      /OPENAI_API_KEY is required for live-model validation\./
    );
  } finally {
    restoreEnv("MODEL", previousModel);
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("OPENAI_BASE_URL", previousBaseUrl);
  }
});

test("buildChatCompletionRequestBody omits temperature for gpt-5-family models", () => {
  const body = buildChatCompletionRequestBody({
    model: "gpt-5-mini",
    userIntent: "Create the admin event.",
    tools: []
  });

  assert.equal("temperature" in body, false);
});

test("buildChatCompletionRequestBody keeps temperature for gpt-4o-mini", () => {
  const body = buildChatCompletionRequestBody({
    model: "gpt-4o-mini",
    userIntent: "Create the admin event.",
    tools: []
  });

  assert.equal(body.temperature, 0);
});

test("buildChatCompletionRequestBody keeps temperature for exact Ollama model ids", () => {
  const body = buildChatCompletionRequestBody({
    model: "qwen2.5:1.5b-instruct",
    userIntent: "Create the admin event.",
    tools: []
  });

  assert.equal(body.temperature, 0);
});

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[name];
    return;
  }

  process.env[name] = value;
}
