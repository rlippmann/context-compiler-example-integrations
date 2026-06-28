import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export type ExpenseRequest = {
  expenseId: string;
  employeeId: string;
  amountUsd: number;
  note: string;
};

export type ExpenseSubmission = {
  expenseId: string;
  employeeId: string;
  amountUsd: number;
  note: string;
};

export type ExpenseExecutionResult = {
  authorizationState: "authorized" | "blocked";
  executed: boolean;
  blockedReason: string | null;
  submission: ExpenseSubmission | null;
  executionLog: string[];
};

export type ExpenseTurnResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  executionResult: ExpenseExecutionResult;
};

export class ExpenseHost {
  public readonly executionLog: string[] = [];

  public submitExpense(request: ExpenseRequest): ExpenseSubmission {
    this.executionLog.push(`submitted:${request.expenseId}`);
    return {
      expenseId: request.expenseId,
      employeeId: request.employeeId,
      amountUsd: request.amountUsd,
      note: request.note
    };
  }
}

export function expenseExecutionIsAuthorized(state: EngineState): boolean {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has("expense_approval")) {
    return false;
  }

  return useItems.has("expense_approval");
}

export function executeExpenseIfAuthorized(
  request: ExpenseRequest,
  state: EngineState,
  host: ExpenseHost
): ExpenseExecutionResult {
  if (!expenseExecutionIsAuthorized(state)) {
    return {
      authorizationState: "blocked",
      executed: false,
      blockedReason: "expense_approval state not authorized",
      submission: null,
      executionLog: [...host.executionLog]
    };
  }

  const submission = host.submitExpense(request);
  return {
    authorizationState: "authorized",
    executed: true,
    blockedReason: null,
    submission,
    executionLog: [...host.executionLog]
  };
}

export function handleExpenseTurn(
  engine: ReturnType<typeof createEngine>,
  compilerInput: string,
  request: ExpenseRequest,
  host: ExpenseHost
): ExpenseTurnResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      executionResult: {
        authorizationState: "blocked",
        executed: false,
        blockedReason: "clarification required before expense execution",
        submission: null,
        executionLog: [...host.executionLog]
      }
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    executionResult: executeExpenseIfAuthorized(request, authoritativeState, host)
  };
}

export function runExample(): ExpenseExecutionResult {
  const engine = createEngine();
  engine.step("use expense_approval");

  const request: ExpenseRequest = {
    expenseId: "expense-100",
    employeeId: "employee-123",
    amountUsd: 245,
    note: "Taxi from airport to client office."
  };
  const host = new ExpenseHost();

  return executeExpenseIfAuthorized(request, engine.state, host);
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: execution authorization with expense approval");
  console.log(JSON.stringify(result, null, 2));
}
