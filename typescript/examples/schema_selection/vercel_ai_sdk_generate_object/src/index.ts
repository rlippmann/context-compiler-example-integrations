import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";
import { z, type ZodTypeAny } from "zod";

declare const process: { argv: string[]; exitCode?: number };

export type StructuredSchemaName = "python_script" | "shell_command";

export type StructuredSchema = {
  name: StructuredSchemaName;
  description: string;
  schema: ZodTypeAny;
};

export type GenerateObjectRequest = {
  prompt: string;
  schemaName: StructuredSchemaName;
  schema: StructuredSchema;
};

export type GenerateObjectLike<TObject> = (
  request: GenerateObjectRequest
) => Promise<{ object: TObject }>;

const PYTHON_SCRIPT_SCHEMA = z.object({
  code: z.string().describe("A complete Python script.")
});

const SHELL_COMMAND_SCHEMA = z.object({
  command: z.string().describe("A single shell command.")
});

const SCHEMA_REGISTRY: Record<StructuredSchemaName, StructuredSchema> = {
  python_script: {
    name: "python_script",
    description: "Generate a Python script object.",
    schema: PYTHON_SCRIPT_SCHEMA
  },
  shell_command: {
    name: "shell_command",
    description: "Generate a shell command object.",
    schema: SHELL_COMMAND_SCHEMA
  }
};

const KNOWN_SCHEMAS: readonly StructuredSchemaName[] = [
  "python_script",
  "shell_command"
];

export function selectStructuredSchemasFromState(
  state: EngineState
): StructuredSchema[] {
  const useItems = getPolicyItems(state, POLICY_USE).filter(
    (item): item is StructuredSchemaName =>
      KNOWN_SCHEMAS.includes(item as StructuredSchemaName)
  );
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (useItems.length > 0) {
    return useItems
      .filter((item) => !prohibitItems.has(item))
      .map((item) => SCHEMA_REGISTRY[item]);
  }

  return [];
}

export function buildGenerateObjectRequest(
  state: EngineState,
  prompt: string
): GenerateObjectRequest | null {
  const availableSchemas = selectStructuredSchemasFromState(state);
  const selected = availableSchemas[0];

  if (!selected) {
    return null;
  }

  return {
    prompt,
    schemaName: selected.name,
    schema: selected
  };
}

export async function generateStructuredObject<TObject>(
  state: EngineState,
  prompt: string,
  generateObject: GenerateObjectLike<TObject>
): Promise<{ request: GenerateObjectRequest; object: TObject } | null> {
  const request = buildGenerateObjectRequest(state, prompt);
  if (request === null) {
    return null;
  }

  const result = await generateObject(request);
  return {
    request,
    object: result.object
  };
}

export async function runExample(): Promise<{
  availableSchemaNames: StructuredSchemaName[];
  requestBuilt: boolean;
  object: { code: string } | null;
}> {
  const engine = createEngine();
  engine.step("use python_script");
  engine.step("prohibit shell_command");

  const availableSchemas = selectStructuredSchemasFromState(engine.state);
  const generated = await generateStructuredObject<{ code: string }>(
    engine.state,
    "Write a short Python script that prints hello.",
    async (request) => ({
      object: {
        code: `# schema=${request.schemaName}\nprint("hello")`
      }
    })
  );

  return {
    availableSchemaNames: availableSchemas.map((schema) => schema.name),
    requestBuilt: generated !== null,
    object: generated?.object ?? null
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  runExample()
    .then((result) => {
      console.log(
        "integration example: schema selection with vercel ai sdk generateObject"
      );
      console.log(JSON.stringify(result, null, 2));
    })
    .catch((error: unknown) => {
      console.error(error);
      process.exitCode = 1;
    });
}
