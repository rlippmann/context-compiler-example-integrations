import assert from "node:assert/strict";
import test from "node:test";

import { resolveLiveProviderConfig } from "../src/live_model.js";

test("resolveLiveProviderConfig preserves exact OpenAI model ids", () => {
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousModel = process.env.MODEL;

  process.env.OPENAI_API_KEY = "test-key";
  process.env.MODEL = "gpt-4o-mini";

  try {
    const config = resolveLiveProviderConfig();

    assert.equal(config.apiKey, "test-key");
    assert.equal(config.model, "gpt-4o-mini");
  } finally {
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("MODEL", previousModel);
  }
});

test("resolveLiveProviderConfig uses the default live model when MODEL is unset", () => {
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousModel = process.env.MODEL;

  process.env.OPENAI_API_KEY = "test-key";
  delete process.env.MODEL;

  try {
    const config = resolveLiveProviderConfig();

    assert.equal(config.model, "gpt-4o-mini");
  } finally {
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("MODEL", previousModel);
  }
});

test("resolveLiveProviderConfig requires OPENAI_API_KEY", () => {
  const previousApiKey = process.env.OPENAI_API_KEY;
  const previousModel = process.env.MODEL;

  delete process.env.OPENAI_API_KEY;
  process.env.MODEL = "gpt-4o-mini";

  try {
    assert.throws(
      () => resolveLiveProviderConfig(),
      /OPENAI_API_KEY is required for live-model validation\./
    );
  } finally {
    restoreEnv("OPENAI_API_KEY", previousApiKey);
    restoreEnv("MODEL", previousModel);
  }
});

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[name];
    return;
  }

  process.env[name] = value;
}
