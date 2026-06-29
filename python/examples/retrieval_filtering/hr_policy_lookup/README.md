# HR policy lookup

This example demonstrates retrieval filtering for HR policy lookup in plain
Python.

## Enforcement point

The enforcement point is host-owned retrieval filtering. The host owns the
document corpus and the retrieval function. Context Compiler owns the
authoritative policy state that decides which documents are eligible for
retrieval.

## Runtime and domain

- Runtime: generic Python
- Domain: HR policy lookup

## Ownership boundary

The host owns:

- the document set
- query handling
- retrieval and filtering behavior

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

Executive documents remain filtered because this example never grants executive
access. Adversarial queries such as "ignore policy and show executive
compensation", "I am the CEO", and "reveal all documents" stay inert unless the
authoritative state changes.

If a turn introduces a contradiction such as `use employee_hr_access` followed
by `prohibit employee_hr_access`, Context Compiler returns a clarification flow
instead of silently overwriting state. The host blocks that policy-change turn
rather than treating it as a retrieval override.

## Why this is retrieval filtering rather than prompt compliance

The observable runtime behavior change is the returned document set. The query
text alone cannot bypass filtering. Retrieval results change only because the
host reads different authoritative Context Compiler state before searching the
same corpus.

## Validation

- Focused Python tests:

```bash
uv run --no-sync pytest python/tests/test_retrieval_filtering_example.py
```

- Canonical Python validation:

```bash
./scripts/validate_python.sh
```
