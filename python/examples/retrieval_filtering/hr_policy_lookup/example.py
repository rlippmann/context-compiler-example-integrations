"""Minimal retrieval-filtering example for HR policy lookup."""

from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from context_compiler import (
    POLICY_PROHIBIT,
    POLICY_USE,
    State,
    create_engine,
    get_decision_state,
    get_policy_items,
    is_clarify,
)
from context_compiler.engine import Engine

EMPLOYEE_ACCESS = "employee_hr_access"
MANAGER_ACCESS = "manager_hr_access"


class PolicyDocument(TypedDict):
    document_id: str
    title: str
    audience: Literal["employee", "manager", "executive"]
    keywords: list[str]
    content: str


class RetrievalResult(TypedDict):
    query: str
    eligible_document_ids: list[str]
    returned_document_ids: list[str]
    blocked_reason: str | None


class RetrievalTurnResult(TypedDict):
    decision_kind: Literal["clarify", "update", "passthrough"]
    prompt_to_user: str | None
    retrieval_result: RetrievalResult


@dataclass
class HRPolicyRetriever:
    """Host-owned retrieval implementation with deterministic filtering."""

    documents: list[PolicyDocument] = field(default_factory=list)

    def search(self, query: str, *, allowed_audiences: set[str]) -> RetrievalResult:
        eligible_documents = [
            document
            for document in self.documents
            if document["audience"] in allowed_audiences
        ]
        normalized_query_terms = set(query.lower().split())
        returned_documents = [
            document
            for document in eligible_documents
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
            "content": "General HR policy, leave policy, and workplace expectations.",
        },
        {
            "document_id": "manager_handbook",
            "title": "Manager Handbook",
            "audience": "manager",
            "keywords": ["manager", "handbook", "approvals", "staffing"],
            "content": "Manager escalation guidance, staffing policy, and approvals.",
        },
        {
            "document_id": "executive_compensation_policy",
            "title": "Executive Compensation Policy",
            "audience": "executive",
            "keywords": ["executive", "compensation", "bonus", "board"],
            "content": "Executive compensation bands, board review, and bonus structure.",
        },
    ]


def _decision_kind_name(
    decision: object,
) -> Literal["clarify", "update", "passthrough"]:
    if not isinstance(decision, dict):
        raise ValueError("unexpected decision shape")

    kind = decision.get("kind")
    kind_name = getattr(kind, "value", None)
    if kind_name not in {"clarify", "update", "passthrough"}:
        raise ValueError(f"unexpected decision kind: {kind_name}")
    return cast(Literal["clarify", "update", "passthrough"], kind_name)


def allowed_audiences_from_state(state: State) -> set[str]:
    """Read allowed retrieval audiences from authoritative compiler state."""

    use_items = set(get_policy_items(state, POLICY_USE))
    prohibit_items = set(get_policy_items(state, POLICY_PROHIBIT))

    if MANAGER_ACCESS in prohibit_items:
        return set()

    if MANAGER_ACCESS in use_items:
        return {"employee", "manager"}

    if EMPLOYEE_ACCESS in prohibit_items:
        return set()

    if EMPLOYEE_ACCESS in use_items:
        return {"employee"}

    return set()


def retrieve_hr_documents(
    query: str,
    *,
    state: State,
    retriever: HRPolicyRetriever,
) -> RetrievalResult:
    """Retrieve only documents the host deems eligible from compiler state."""

    return retriever.search(
        query,
        allowed_audiences=allowed_audiences_from_state(state),
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

    if is_clarify(decision):
        return {
            "decision_kind": "clarify",
            "prompt_to_user": decision.get("prompt_to_user"),
            "retrieval_result": {
                "query": query,
                "eligible_document_ids": [],
                "returned_document_ids": [],
                "blocked_reason": "clarification required before retrieval policy changes",
            },
        }

    authoritative_state = get_decision_state(decision)
    if authoritative_state is None:
        authoritative_state = engine.state

    return {
        "decision_kind": _decision_kind_name(decision),
        "prompt_to_user": decision.get("prompt_to_user"),
        "retrieval_result": retrieve_hr_documents(
            query,
            state=authoritative_state,
            retriever=retriever,
        ),
    }


def run_demo() -> dict[str, RetrievalResult]:
    """Run a deterministic retrieval-filtering demonstration."""

    query = "handbook policy"
    retriever = HRPolicyRetriever(documents=example_documents())

    absent_engine = create_engine()
    employee_engine = create_engine()
    employee_engine.step(f"use {EMPLOYEE_ACCESS}")
    manager_engine = create_engine()
    manager_engine.step(f"use {MANAGER_ACCESS}")

    return {
        "absent_state": retrieve_hr_documents(
            query,
            state=absent_engine.state,
            retriever=retriever,
        ),
        "employee_access": retrieve_hr_documents(
            query,
            state=employee_engine.state,
            retriever=retriever,
        ),
        "manager_access": retrieve_hr_documents(
            query,
            state=manager_engine.state,
            retriever=retriever,
        ),
    }


if __name__ == "__main__":
    print(run_demo())
