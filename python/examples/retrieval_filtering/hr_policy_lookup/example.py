"""Minimal retrieval-filtering example for HR policy lookup."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from context_compiler import (
    Decision,
    DecisionKind,
    POLICY_PROHIBIT,
    POLICY_USE,
    PolicyValue,
    Engine,
)

EMPLOYEE_ACCESS = "employee_hr_access"
MANAGER_ACCESS = "manager_hr_access"
LEAVE_CASE_PREMISE = "case concerns leave eligibility after a parental leave request"
GENERAL_HANDBOOK_PREMISE = (
    "case concerns general employee handbook expectations for a new hire"
)
STAFFING_CASE_PREMISE = "case concerns staffing approval for a team reorganization"


class PolicyDocument(TypedDict):
    document_id: str
    title: str
    audience: Literal["employee", "manager", "executive"]
    keywords: list[str]
    relevance_tags: list[str]
    content: str


class RetrievalResult(TypedDict):
    query: str
    eligible_document_ids: list[str]
    returned_document_ids: list[str]
    blocked_reason: str | None


class RetrievalTurnResult(TypedDict):
    decision_kind: Literal["error", "update", "passthrough"]
    prompt_to_user: str | None
    retrieval_result: RetrievalResult


CaseContext = Literal["general_handbook_case", "leave_case", "staffing_case"]


@dataclass
class HRPolicyRetriever:
    """Host-owned retrieval implementation with deterministic filtering."""

    documents: list[PolicyDocument] = field(default_factory=list)

    def search(
        self,
        query: str,
        *,
        allowed_audiences: set[str],
        case_context: CaseContext | None,
    ) -> RetrievalResult:
        eligible_documents = [
            document
            for document in self.documents
            if document["audience"] in allowed_audiences
        ]
        relevance_filtered_documents = filter_documents_by_case_context(
            eligible_documents,
            case_context,
        )
        normalized_query_terms = set(query.lower().split())
        returned_documents = [
            document
            for document in relevance_filtered_documents
            if normalized_query_terms & set(document["keywords"])
        ]

        return {
            "query": query,
            "eligible_document_ids": [
                document["document_id"] for document in eligible_documents
            ],
            "returned_document_ids": [
                document["document_id"] for document in returned_documents
            ],
            "blocked_reason": None,
        }


def example_documents() -> list[PolicyDocument]:
    return [
        {
            "document_id": "employee_handbook",
            "title": "Employee Handbook",
            "audience": "employee",
            "keywords": ["employee", "handbook", "benefits", "leave"],
            "relevance_tags": ["general_handbook_case", "general_hr"],
            "content": "General HR policy, leave policy, and workplace expectations.",
        },
        {
            "document_id": "leave_of_absence_policy",
            "title": "Leave of Absence Policy",
            "audience": "employee",
            "keywords": ["leave", "eligibility", "parental"],
            "relevance_tags": ["leave_case"],
            "content": "Leave eligibility, parental leave steps, and required documentation.",
        },
        {
            "document_id": "manager_handbook",
            "title": "Manager Handbook",
            "audience": "manager",
            "keywords": ["manager", "handbook", "approvals", "staffing"],
            "relevance_tags": ["general_handbook_case", "staffing_case"],
            "content": "Manager escalation guidance, staffing policy, and approvals.",
        },
        {
            "document_id": "executive_compensation_policy",
            "title": "Executive Compensation Policy",
            "audience": "executive",
            "keywords": ["executive", "compensation", "bonus", "board"],
            "relevance_tags": ["executive_only"],
            "content": "Executive compensation bands, board review, and bonus structure.",
        },
    ]


def _decision_kind_name(
    decision: Decision,
) -> Literal["error", "update", "passthrough"]:
    kind = decision.kind
    if kind == DecisionKind.ERROR:
        return "error"
    if kind == DecisionKind.UPDATE:
        return "update"
    if kind == DecisionKind.NO_DIRECTIVE:
        return "passthrough"
    raise ValueError(f"unexpected decision kind: {kind}")


def allowed_audiences_from_policies(policies: Mapping[str, PolicyValue]) -> set[str]:
    """Read allowed retrieval audiences from authoritative compiler state."""

    if policies.get(MANAGER_ACCESS) == POLICY_PROHIBIT:
        return set()

    if policies.get(MANAGER_ACCESS) == POLICY_USE:
        return {"employee", "manager"}

    if policies.get(EMPLOYEE_ACCESS) == POLICY_PROHIBIT:
        return set()

    if policies.get(EMPLOYEE_ACCESS) == POLICY_USE:
        return {"employee"}

    return set()


def classify_premise_as_case_context(premise: str | None) -> CaseContext | None:
    """Map saved HR case facts to a host-owned retrieval relevance context."""

    if premise is None:
        return None

    normalized_premise = premise.casefold()
    if (
        "general employee handbook" in normalized_premise
        and "new hire" in normalized_premise
    ):
        return "general_handbook_case"

    if (
        "leave eligibility" in normalized_premise
        and "parental leave" in normalized_premise
    ):
        return "leave_case"

    if (
        "staffing approval" in normalized_premise
        and "team reorganization" in normalized_premise
    ):
        return "staffing_case"

    return None


def filter_documents_by_case_context(
    documents: list[PolicyDocument],
    case_context: CaseContext | None,
) -> list[PolicyDocument]:
    """Limit relevance only within the already eligible document set."""

    if case_context is None:
        return [
            document
            for document in documents
            if "general_handbook_case" in document["relevance_tags"]
        ]

    relevant_documents = [
        document for document in documents if case_context in document["relevance_tags"]
    ]
    if relevant_documents:
        return relevant_documents

    return []


def retrieve_hr_documents(
    query: str,
    *,
    premise: str | None,
    policies: Mapping[str, PolicyValue],
    retriever: HRPolicyRetriever,
) -> RetrievalResult:
    """Retrieve only documents the host deems eligible from compiler state."""

    return retriever.search(
        query,
        allowed_audiences=allowed_audiences_from_policies(policies),
        case_context=classify_premise_as_case_context(premise),
    )


def handle_retrieval_turn(
    engine: Engine,
    *,
    compiler_input: str,
    query: str,
    retriever: HRPolicyRetriever,
) -> RetrievalTurnResult:
    """Resolve policy updates, but block retrieval on contradictory turns."""

    decision = engine.step(compiler_input)

    if decision.kind == DecisionKind.ERROR:
        return {
            "decision_kind": "error",
            "prompt_to_user": decision.message
            if decision.kind == DecisionKind.ERROR
            else None,
            "retrieval_result": {
                "query": query,
                "eligible_document_ids": [],
                "returned_document_ids": [],
                "blocked_reason": "compiler rejected retrieval policy change",
            },
        }

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.message
        if decision.kind == DecisionKind.ERROR
        else None,
        "retrieval_result": retrieve_hr_documents(
            query,
            premise=engine.premise,
            policies=engine.policies,
            retriever=retriever,
        ),
    }


def run_demo() -> dict[str, RetrievalResult]:
    """Run a deterministic retrieval-filtering demonstration."""

    query = "handbook policy"
    retriever = HRPolicyRetriever(documents=example_documents())

    absent_engine = Engine()
    employee_engine = Engine()
    employee_engine.step(f"use {EMPLOYEE_ACCESS}")
    manager_engine = Engine()
    manager_engine.step(f"use {MANAGER_ACCESS}")

    return {
        "absent_state": retrieve_hr_documents(
            query,
            premise=absent_engine.premise,
            policies=absent_engine.policies,
            retriever=retriever,
        ),
        "employee_access": retrieve_hr_documents(
            query,
            premise=employee_engine.premise,
            policies=employee_engine.policies,
            retriever=retriever,
        ),
        "manager_access": retrieve_hr_documents(
            query,
            premise=manager_engine.premise,
            policies=manager_engine.policies,
            retriever=retriever,
        ),
    }


if __name__ == "__main__":
    print(run_demo())
