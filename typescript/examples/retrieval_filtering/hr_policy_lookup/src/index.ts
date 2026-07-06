import {
  POLICY_PROHIBIT,
  POLICY_USE,
  createEngine,
  getPolicyItems,
  getPremiseValue,
  type Engine,
  type EngineState
} from "@rlippmann/context-compiler";

declare const process: { argv: string[]; exitCode?: number };

export const EMPLOYEE_ACCESS = "employee_hr_access";
export const MANAGER_ACCESS = "manager_hr_access";
export const LEAVE_CASE_PREMISE =
  "case concerns leave eligibility after a parental leave request";
export const GENERAL_HANDBOOK_PREMISE =
  "case concerns general employee handbook expectations for a new hire";
export const STAFFING_CASE_PREMISE =
  "case concerns staffing approval for a team reorganization";

export type PolicyDocument = {
  documentId: string;
  title: string;
  audience: "employee" | "manager" | "executive";
  keywords: string[];
  relevanceTags: string[];
  content: string;
};

export type RetrievalResult = {
  query: string;
  eligibleDocumentIds: string[];
  returnedDocumentIds: string[];
  blockedReason: string | null;
};

export type RetrievalTurnResult = {
  decisionKind: "clarify" | "update" | "passthrough";
  promptToUser: string | null;
  retrievalResult: RetrievalResult;
};

export type CaseContext = "general_handbook_case" | "leave_case" | "staffing_case";

export class HRPolicyRetriever {
  public constructor(public readonly documents: PolicyDocument[]) {}

  public search(
    query: string,
    allowedAudiences: Set<string>,
    caseContext: CaseContext | null
  ): RetrievalResult {
    const eligibleDocuments = this.documents.filter((document) =>
      allowedAudiences.has(document.audience)
    );
    const relevanceFilteredDocuments = filterDocumentsByCaseContext(
      eligibleDocuments,
      caseContext
    );
    const normalizedQueryTerms = new Set(query.toLowerCase().split(/\s+/));
    const returnedDocuments = relevanceFilteredDocuments.filter((document) => {
      const searchableTerms = new Set(document.keywords);
      return [...normalizedQueryTerms].some((term) => searchableTerms.has(term));
    });

    return {
      query,
      eligibleDocumentIds: eligibleDocuments.map((document) => document.documentId),
      returnedDocumentIds: returnedDocuments.map((document) => document.documentId),
      blockedReason: null
    };
  }
}

export function exampleDocuments(): PolicyDocument[] {
  return [
    {
      documentId: "employee_handbook",
      title: "Employee Handbook",
      audience: "employee",
      keywords: ["employee", "handbook", "benefits", "leave"],
      relevanceTags: ["general_handbook_case", "general_hr"],
      content: "General HR policy, leave policy, and workplace expectations."
    },
    {
      documentId: "leave_of_absence_policy",
      title: "Leave of Absence Policy",
      audience: "employee",
      keywords: ["leave", "eligibility", "parental"],
      relevanceTags: ["leave_case"],
      content: "Leave eligibility, parental leave steps, and required documentation."
    },
    {
      documentId: "manager_handbook",
      title: "Manager Handbook",
      audience: "manager",
      keywords: ["manager", "handbook", "approvals", "staffing"],
      relevanceTags: ["general_handbook_case", "staffing_case"],
      content: "Manager escalation guidance, staffing policy, and approvals."
    },
    {
      documentId: "executive_compensation_policy",
      title: "Executive Compensation Policy",
      audience: "executive",
      keywords: ["executive", "compensation", "bonus", "board"],
      relevanceTags: ["executive_only"],
      content: "Executive compensation bands, board review, and bonus structure."
    }
  ];
}

export function allowedAudiencesFromState(state: EngineState): Set<string> {
  const useItems = new Set(getPolicyItems(state, POLICY_USE));
  const prohibitItems = new Set(getPolicyItems(state, POLICY_PROHIBIT));

  if (prohibitItems.has(MANAGER_ACCESS)) {
    return new Set();
  }

  if (useItems.has(MANAGER_ACCESS)) {
    return new Set(["employee", "manager"]);
  }

  if (prohibitItems.has(EMPLOYEE_ACCESS)) {
    return new Set();
  }

  if (useItems.has(EMPLOYEE_ACCESS)) {
    return new Set(["employee"]);
  }

  return new Set();
}

export function classifyPremiseAsCaseContext(premise: string | null): CaseContext | null {
  if (premise === null) {
    return null;
  }

  const normalizedPremise = premise.toLowerCase();
  if (
    normalizedPremise.includes("general employee handbook") &&
    normalizedPremise.includes("new hire")
  ) {
    return "general_handbook_case";
  }

  if (
    normalizedPremise.includes("leave eligibility") &&
    normalizedPremise.includes("parental leave")
  ) {
    return "leave_case";
  }

  if (
    normalizedPremise.includes("staffing approval") &&
    normalizedPremise.includes("team reorganization")
  ) {
    return "staffing_case";
  }

  return null;
}

export function filterDocumentsByCaseContext(
  documents: PolicyDocument[],
  caseContext: CaseContext | null
): PolicyDocument[] {
  if (caseContext === null) {
    return documents.filter((document) =>
      document.relevanceTags.includes("general_handbook_case")
    );
  }

  const relevantDocuments = documents.filter((document) =>
    document.relevanceTags.includes(caseContext)
  );
  if (relevantDocuments.length > 0) {
    return relevantDocuments;
  }

  return [];
}

export function retrieveHrDocuments(
  query: string,
  state: EngineState,
  retriever: HRPolicyRetriever
): RetrievalResult {
  return retriever.search(
    query,
    allowedAudiencesFromState(state),
    classifyPremiseAsCaseContext(getPremiseValue(state))
  );
}

export function handleRetrievalTurn(
  engine: Engine,
  compilerInput: string,
  query: string,
  retriever: HRPolicyRetriever
): RetrievalTurnResult {
  const decision = engine.step(compilerInput);

  if (decision.kind === "clarify") {
    return {
      decisionKind: "clarify",
      promptToUser: decision.prompt_to_user,
      retrievalResult: {
        query,
        eligibleDocumentIds: [],
        returnedDocumentIds: [],
        blockedReason: "clarification required before retrieval policy changes"
      }
    };
  }

  const authoritativeState = decision.state ?? engine.state;

  return {
    decisionKind: decision.kind,
    promptToUser: decision.prompt_to_user,
    retrievalResult: retrieveHrDocuments(query, authoritativeState, retriever)
  };
}

export function runExample(): Record<string, RetrievalResult> {
  const query = "handbook policy";
  const retriever = new HRPolicyRetriever(exampleDocuments());

  const absentEngine = createEngine();
  const employeeEngine = createEngine();
  employeeEngine.step(`use ${EMPLOYEE_ACCESS}`);
  const managerEngine = createEngine();
  managerEngine.step(`use ${MANAGER_ACCESS}`);

  return {
    absentState: retrieveHrDocuments(query, absentEngine.state, retriever),
    employeeAccess: retrieveHrDocuments(query, employeeEngine.state, retriever),
    managerAccess: retrieveHrDocuments(query, managerEngine.state, retriever)
  };
}

if (
  typeof process !== "undefined" &&
  process.argv[1] &&
  import.meta.url === new URL(process.argv[1], "file://").href
) {
  const result = runExample();
  console.log("integration example: retrieval filtering with HR policy lookup");
  console.log(JSON.stringify(result, null, 2));
}
