"""ChromaDB retrieval filtering for HR policy lookup."""

from dataclasses import dataclass
from typing import Any, Literal, Sequence, TypedDict, cast
from uuid import uuid4

import chromadb
from chromadb.api.models.Collection import Collection
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

KEYWORD_DIMENSIONS = (
    "employee",
    "manager",
    "executive",
    "handbook",
    "benefits",
    "approvals",
    "compensation",
)


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


def query_embedding(query: str) -> list[float]:
    """Create a deterministic local embedding without any model call."""

    normalized_terms = set(query.lower().split())
    return [
        1.0 if dimension in normalized_terms else 0.0
        for dimension in KEYWORD_DIMENSIONS
    ]


def document_embedding(document: PolicyDocument) -> list[float]:
    keyword_set = set(document["keywords"])
    return [
        1.0 if dimension in keyword_set else 0.0 for dimension in KEYWORD_DIMENSIONS
    ]


def audience_filter(allowed_audiences: set[str]) -> dict[str, object]:
    return {"audience": {"$in": sorted(allowed_audiences)}}


@dataclass
class ChromaHRPolicyRetriever:
    """Host-owned retriever backed by a local Chroma collection."""

    collection: Collection
    documents: list[PolicyDocument]

    @classmethod
    def build(
        cls,
        *,
        documents: list[PolicyDocument] | None = None,
    ) -> "ChromaHRPolicyRetriever":
        if documents is None:
            documents = example_documents()

        client = chromadb.EphemeralClient()
        collection = client.create_collection(
            name=f"hr-policy-{uuid4()}",
            metadata={"description": "HR policy retrieval filtering example"},
        )
        document_embeddings = cast(
            list[Sequence[float]],
            [document_embedding(document) for document in documents],
        )
        collection.add(
            ids=[document["document_id"] for document in documents],
            documents=[document["content"] for document in documents],
            metadatas=[
                {
                    "audience": document["audience"],
                    "title": document["title"],
                }
                for document in documents
            ],
            embeddings=document_embeddings,
        )
        return cls(collection=collection, documents=documents)

    def search(self, query: str, *, allowed_audiences: set[str]) -> RetrievalResult:
        if not allowed_audiences:
            return {
                "query": query,
                "eligible_document_ids": [],
                "returned_document_ids": [],
                "blocked_reason": None,
            }

        where = cast(Any, audience_filter(allowed_audiences))
        eligible = self.collection.get(where=where)
        query_vector = cast(list[Sequence[float]], [query_embedding(query)])
        query_results = self.collection.query(
            query_embeddings=query_vector,
            n_results=len(self.documents),
            where=where,
        )

        eligible_document_ids = sorted(cast(list[str], eligible["ids"]))
        returned_document_ids = self._rank_matching_documents(
            query,
            candidate_ids=cast(list[str], query_results["ids"][0]),
            eligible_document_ids=eligible_document_ids,
        )

        return {
            "query": query,
            "eligible_document_ids": eligible_document_ids,
            "returned_document_ids": returned_document_ids,
            "blocked_reason": None,
        }

    def _rank_matching_documents(
        self,
        query: str,
        *,
        candidate_ids: list[str],
        eligible_document_ids: list[str],
    ) -> list[str]:
        normalized_query_terms = set(query.lower().split())
        documents_by_id = {
            document["document_id"]: document for document in self.documents
        }
        scored_matches: list[tuple[int, str]] = []

        for document_id in candidate_ids:
            if document_id not in eligible_document_ids:
                continue

            keyword_overlap = len(
                normalized_query_terms & set(documents_by_id[document_id]["keywords"])
            )
            if keyword_overlap == 0:
                continue

            scored_matches.append((keyword_overlap, document_id))

        scored_matches.sort(key=lambda item: (-item[0], item[1]))
        return [document_id for _, document_id in scored_matches]


def retrieve_hr_documents(
    query: str,
    *,
    state: State,
    retriever: ChromaHRPolicyRetriever,
) -> RetrievalResult:
    """Apply eligibility constraints before Chroma returns any documents."""

    return retriever.search(
        query,
        allowed_audiences=allowed_audiences_from_state(state),
    )


def handle_retrieval_turn(
    engine: Engine,
    *,
    compiler_input: str,
    query: str,
    retriever: ChromaHRPolicyRetriever,
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
    """Run a deterministic ChromaDB retrieval-filtering demonstration."""

    query = "handbook benefits"
    retriever = ChromaHRPolicyRetriever.build()

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
