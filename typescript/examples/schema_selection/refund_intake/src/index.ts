import {
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

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

export function selectSchemaFromState(state: EngineState): string | null {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));

  if (useItems.has("refund_intake")) {
    return "refund_intake";
  }

  if (useItems.has("technical_support")) {
    return "technical_support";
  }

  return null;
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
