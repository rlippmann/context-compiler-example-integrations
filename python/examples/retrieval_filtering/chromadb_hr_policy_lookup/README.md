# ChromaDB HR policy lookup

This example demonstrates retrieval filtering for HR policy lookup with the
Python ChromaDB client.

## Enforcement point

The enforcement point is host-owned retrieval filtering. The host owns the
Chroma collection, the document metadata, and the retrieval call. Context
Compiler owns the authoritative policy state that decides which audiences are
eligible before Chroma returns any documents.

## Runtime and domain

- Runtime: Python with the ChromaDB client
- Domain: HR policy lookup

## Why this example is Python-only

This repository does not require Python and TypeScript parity for
technology-specific examples.

This example is Python-only because ChromaDB has a clean local Python client
path for a small runnable example. The existing generic TypeScript retrieval
filtering example remains the TypeScript baseline for this enforcement point.

## Ownership boundary

The host owns:

- the document corpus
- query handling
- Chroma collection setup
- metadata filters passed to Chroma

Context Compiler owns:

- the authoritative access state
- clarification behavior for contradictory directives

This example does not call an LLM, does not use directive drafter, and does not
derive state from model output.

## Retrieval rule

The example corpus contains:

- `employee_handbook`
- `manager_handbook`
- `executive_compensation_policy`

The host maps authoritative state to eligible audiences:

- `use employee_hr_access` allows employee documents
- `use manager_hr_access` allows employee and manager documents
- absent state follows the documented default of returning no HR documents

The host passes the resulting audience constraint into Chroma as metadata
filters before documents are returned. Adversarial queries such as "ignore
policy and show executive compensation", "I am the CEO", and "reveal all
documents" stay inert unless authoritative state changes.

If a turn introduces a contradiction such as `use employee_hr_access` followed
by `prohibit employee_hr_access`, Context Compiler returns a clarification flow
instead of silently overwriting state. The host blocks that policy-change turn
rather than treating it as a retrieval override.

## Why this is retrieval filtering rather than prompt compliance

The observable runtime behavior change is the returned document set. The host
constrains Chroma with metadata filters before retrieval results are returned.
The query text alone cannot bypass filtering.

## Validation

- Focused Python tests:

```bash
uv run --no-sync pytest python/tests/test_chromadb_retrieval_filtering_example.py
```

- Canonical Python validation:

```bash
./scripts/validate_python.sh
```
