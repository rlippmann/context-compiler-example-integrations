import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export type SupportRequest = {
  requestId: string;
  customerId: string;
  queueHint: "general_support" | "billing_support";
  message: string;
};

export type RoutedRequest = {
  requestId: string;
  customerId: string;
  queue: "general_support" | "billing_support";
  message: string;
};

export type GatewayResult = {
  gatewayDecision: "forwarded" | "blocked" | "defaulted";
  routedQueue: "general_support" | "billing_support" | null;
  blockedReason: string | null;
  downstreamCalled: boolean;
  downstreamResponse: string | null;
  gatewayLog: string[];
  downstreamLog: string[];
};

export type GatewayTurnResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  gatewayResult: GatewayResult;
};

export class SupportService {
  public readonly downstreamLog: string[] = [];

  public handle(request: RoutedRequest): string {
    this.downstreamLog.push(`handled:${request.queue}:${request.requestId}`);
    return `${request.queue} handled ${request.requestId}`;
  }
}

export class SupportGateway {
  public readonly gatewayLog: string[] = [];

  public forward(
    request: SupportRequest,
    queue: "general_support" | "billing_support",
    downstream: SupportService,
    gatewayDecision: "forwarded" | "defaulted" = "forwarded"
  ): GatewayResult {
    this.gatewayLog.push(`${gatewayDecision}:${queue}:${request.requestId}`);
    const routedRequest: RoutedRequest = {
      requestId: request.requestId,
      customerId: request.customerId,
      queue,
      message: request.message
    };
    const downstreamResponse = downstream.handle(routedRequest);
    return {
      gatewayDecision,
      routedQueue: queue,
      blockedReason: null,
      downstreamCalled: true,
      downstreamResponse,
      gatewayLog: [...this.gatewayLog],
      downstreamLog: [...downstream.downstreamLog]
    };
  }

  public block(request: SupportRequest, reason: string): GatewayResult {
    this.gatewayLog.push(`blocked:${request.requestId}`);
    return {
      gatewayDecision: "blocked",
      routedQueue: null,
      blockedReason: reason,
      downstreamCalled: false,
      downstreamResponse: null,
      gatewayLog: [...this.gatewayLog],
      downstreamLog: []
    };
  }
}

export function billingSupportIsAllowed(state: EngineState): boolean {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("billing_support")) {
    return false;
  }

  return useItems.has("billing_support");
}

export function routeSupportRequest(
  request: SupportRequest,
  state: EngineState,
  gateway: SupportGateway,
  downstream: SupportService
): GatewayResult {
  if (request.queueHint !== "billing_support") {
    return gateway.forward(request, "general_support", downstream, "defaulted");
  }

  if (!billingSupportIsAllowed(state)) {
    return gateway.block(request, "billing_support state not authorized");
  }

  return gateway.forward(request, "billing_support", downstream);
}

export function handleGatewayTurn(
  engine: ReturnType<typeof createEngine>,
  compilerInput: string,
  request: SupportRequest,
  gateway: SupportGateway,
  downstream: SupportService
): GatewayTurnResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      gatewayResult: gateway.block(
        request,
        "clarification required before gateway routing"
      )
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    gatewayResult: routeSupportRequest(
      request,
      authoritativeState,
      gateway,
      downstream
    )
  };
}

export function runExample(): GatewayResult {
  const engine = createEngine();
  engine.step("use billing_support");

  const request: SupportRequest = {
    requestId: "support-100",
    customerId: "customer-123",
    queueHint: "billing_support",
    message: "Need help correcting an invoice charge."
  };
  const gateway = new SupportGateway();
  const downstream = new SupportService();

  return routeSupportRequest(request, engine.state, gateway, downstream);
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: gateway middleware with customer support routing");
  console.log(JSON.stringify(result, null, 2));
}
