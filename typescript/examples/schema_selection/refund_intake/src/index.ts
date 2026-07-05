import {
  POLICY_USE,
  createEngine,
  getPolicyItems,
  getPremiseValue,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export const DAMAGED_ORDER_PREMISE =
  "order A-100 is a delivered physical item reported as damaged on arrival";
export const DIGITAL_LOGIN_FAILURE_PREMISE =
  "order A-100 is a digital subscription with an active login failure after purchase";
export type OrderIntakeContext =
  | "damaged_physical_delivery"
  | "digital_subscription_login_failure";

export type IntakeRequest = {
  customerId: string;
  message: string;
};

export type RefundIntakeResult = {
  kind: "refund";
  customerId: string;
  reason: string;
};

export type TechnicalSupportResult = {
  kind: "technical_support";
  customerId: string;
  issue: string;
};

export type IntakeRunResult = {
  selectedSchema: string | null;
  refundHandlerCalled: boolean;
  technicalSupportHandlerCalled: boolean;
  result: RefundIntakeResult | TechnicalSupportResult | null;
};

const SCHEMA_BY_ORDER_INTAKE_CONTEXT: Record<OrderIntakeContext, string> = {
  damaged_physical_delivery: "refund_intake",
  digital_subscription_login_failure: "technical_support"
};

export class IntakeHandler {
  public called = false;

  public constructor(public readonly name: "refund_intake" | "technical_support") {}

  public handle(request: IntakeRequest): RefundIntakeResult | TechnicalSupportResult {
    this.called = true;

    if (this.name === "refund_intake") {
      return {
        kind: "refund",
        customerId: request.customerId,
        reason: request.message
      };
    }

    return {
      kind: "technical_support",
      customerId: request.customerId,
      issue: request.message
    };
  }
}

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
): string | null {
  if (context === null) {
    return null;
  }

  return SCHEMA_BY_ORDER_INTAKE_CONTEXT[context];
}

export function selectSchemaFromState(state: EngineState): string | null {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const premise = getPremiseValue(state);

  if (useItems.has("refund_intake")) {
    return "refund_intake";
  }

  if (useItems.has("technical_support")) {
    return "technical_support";
  }

  const intakeContext = classifyPremiseAsOrderIntakeContext(premise);
  return selectSchemaFromOrderIntakeContext(intakeContext);
}

export function runIntake(
  request: IntakeRequest,
  selectedSchema: string | null,
  refundHandler: IntakeHandler,
  technicalSupportHandler: IntakeHandler
): RefundIntakeResult | TechnicalSupportResult | null {
  if (selectedSchema === "refund_intake") {
    return refundHandler.handle(request);
  }

  if (selectedSchema === "technical_support") {
    return technicalSupportHandler.handle(request);
  }

  return null;
}

export function runExample(): IntakeRunResult {
  const engine = createEngine();
  engine.step("use refund_intake");

  const request: IntakeRequest = {
    customerId: "customer-123",
    message: "I need a refund for order A-100."
  };

  const refundHandler = new IntakeHandler("refund_intake");
  const technicalSupportHandler = new IntakeHandler("technical_support");

  const selectedSchema = selectSchemaFromState(engine.state);
  const result = runIntake(
    request,
    selectedSchema,
    refundHandler,
    technicalSupportHandler
  );

  return {
    selectedSchema,
    refundHandlerCalled: refundHandler.called,
    technicalSupportHandlerCalled: technicalSupportHandler.called,
    result
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: schema selection with refund_intake");
  console.log(JSON.stringify(result, null, 2));
}
