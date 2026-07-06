import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  getPremiseValue,
  type EngineState
} from "@rlippmann/context-compiler";
import { z, type ZodTypeAny } from "zod";

declare const process: { argv: string[]; exitCode?: number };

export type StructuredSchemaName = "refund_intake" | "technical_support";
export const DAMAGED_ORDER_PREMISE =
  "order A-100 is a delivered physical item reported as damaged on arrival";
export const DIGITAL_LOGIN_FAILURE_PREMISE =
  "order A-100 is a digital subscription with an active login failure after purchase";
export type OrderIntakeContext =
  | "damaged_physical_delivery"
  | "digital_subscription_login_failure";

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

const REFUND_INTAKE_SCHEMA = z.object({
  kind: z.literal("refund"),
  customerId: z.string().describe("Customer identifier for the refund request."),
  orderId: z.string().describe("Order identifier for the refund request."),
  reason: z.string().describe("Customer reason for requesting the refund.")
});

const TECHNICAL_SUPPORT_SCHEMA = z.object({
  kind: z.literal("technical_support"),
  customerId: z.string().describe("Customer identifier for the support request."),
  issue: z.string().describe("Customer issue that needs technical support.")
});

const SCHEMA_REGISTRY: Record<StructuredSchemaName, StructuredSchema> = {
  refund_intake: {
    name: "refund_intake",
    description: "Generate a refund intake object.",
    schema: REFUND_INTAKE_SCHEMA
  },
  technical_support: {
    name: "technical_support",
    description: "Generate a technical support intake object.",
    schema: TECHNICAL_SUPPORT_SCHEMA
  }
};

const KNOWN_SCHEMAS: readonly StructuredSchemaName[] = [
  "refund_intake",
  "technical_support"
];

const SCHEMA_BY_ORDER_INTAKE_CONTEXT: Record<
  OrderIntakeContext,
  StructuredSchemaName
> = {
  damaged_physical_delivery: "refund_intake",
  digital_subscription_login_failure: "technical_support"
};

export function classifyPremiseAsOrderIntakeContext(
  premise: string | null
): OrderIntakeContext | null {
  if (premise === null) {
    return null;
  }

  const normalizedPremise = premise.toLowerCase();
  if (
    normalizedPremise.includes("delivered physical item") &&
    normalizedPremise.includes("damaged on arrival")
  ) {
    return "damaged_physical_delivery";
  }

  if (
    normalizedPremise.includes("digital subscription") &&
    normalizedPremise.includes("login failure")
  ) {
    return "digital_subscription_login_failure";
  }

  return null;
}

export function selectSchemaFromOrderIntakeContext(
  context: OrderIntakeContext | null
): StructuredSchemaName | null {
  if (context === null) {
    return null;
  }

  return SCHEMA_BY_ORDER_INTAKE_CONTEXT[context];
}

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

  const intakeContext = classifyPremiseAsOrderIntakeContext(getPremiseValue(state));
  const fallbackSchema = selectSchemaFromOrderIntakeContext(intakeContext);
  if (fallbackSchema !== null) {
    return [SCHEMA_REGISTRY[fallbackSchema]];
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
  object: {
    kind: "refund";
    customerId: string;
    orderId: string;
    reason: string;
  } | null;
}> {
  const engine = createEngine();
  engine.step("use refund_intake");
  engine.step("prohibit technical_support");

  const availableSchemas = selectStructuredSchemasFromState(engine.state);
  const generated = await generateStructuredObject<{
    kind: "refund";
    customerId: string;
    orderId: string;
    reason: string;
  }>(
    engine.state,
    "Customer customer-123 says: I need a refund for order A-100.",
    async (request) => ({
      object: {
        kind: "refund",
        customerId: "customer-123",
        orderId: "A-100",
        reason: `Selected schema: ${request.schemaName}`
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
