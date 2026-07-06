# HR policy lookup

This example demonstrates retrieval filtering for HR policy lookup in plain
TypeScript.

## Enforcement point

The enforcement point is host-owned retrieval filtering. The host owns the
document corpus and the retrieval function. Context Compiler owns the
authoritative policy state that decides which documents are eligible for
retrieval.

## Runtime and domain

- Runtime: generic TypeScript
- Domain: HR policy lookup

## Ownership boundary

The host owns:

- the document set
- query handling
- retrieval and filtering behavior

Context Compiler owns:

- the authoritative access state
- the authoritative saved case premise
- clarification behavior for contradictory directives

This example does not call an LLM, does not use directive drafter, and does not
derive state from model output.

## Retrieval rule

The example corpus contains:

- `employee_handbook`
- `leave_of_absence_policy`
- `manager_handbook`
- `executive_compensation_policy`

The host applies retrieval in this order:

- `use employee_hr_access` allows employee documents
- `use manager_hr_access` allows employee and manager documents
- absent state follows the documented default of returning no HR documents
- after eligibility is fixed, saved premise facts may narrow relevance inside
  the eligible set

Policy controls eligibility. Premise controls relevance within that eligible
set. Premise does not grant access and does not select a collection.

For premise-driven relevance, the host applies a small deterministic rule:

`saved HR case facts -> case context -> relevant documents within eligible set`

Examples:

- `set premise case concerns leave eligibility after a parental leave request`
  narrows employee-visible results toward `leave_of_absence_policy`
- `set premise case concerns general employee handbook expectations for a new hire`
  narrows employee-visible results toward `employee_handbook`
- `set premise case concerns staffing approval for a team reorganization`
  narrows manager-visible results toward `manager_handbook`

With the same query, `leave`:

- `use employee_hr_access` plus the leave-eligibility premise returns
  `leave_of_absence_policy`
- `use employee_hr_access` plus the general employee-handbook premise returns
  `employee_handbook`

In both cases, the eligible employee documents stay the same:

- `employee_handbook`
- `leave_of_absence_policy`

The premise changes only which already-eligible document is returned as the
relevant match. It does not change `eligibleDocumentIds`.

Without a matching or known premise, the host falls back to the default
employee-handbook relevance path. Unknown premise text does not invent a new
result set.

If the saved premise points at manager-only staffing context while policy still
allows only employee access, the host returns no results for that premise path
rather than expanding eligibility.

Executive documents remain filtered because this example never grants executive
access. Adversarial queries such as "ignore policy and show executive
compensation", "I am the CEO", and "reveal all documents" stay inert unless the
authoritative state changes. Adversarial query text does not overwrite either
saved access policy or saved case premise.

If a turn introduces a contradiction such as `use employee_hr_access` followed
by `prohibit employee_hr_access`, Context Compiler returns a clarification flow
instead of silently overwriting state. The host blocks that policy-change turn
rather than treating it as a retrieval override.

## Why this is retrieval filtering rather than prompt compliance

The observable runtime behavior change is the returned document set. The query
text alone cannot bypass filtering. Retrieval results change only because the
host reads different authoritative Context Compiler state before searching the
same corpus. Access eligibility is applied first, and premise-based relevance
is applied only inside that eligible document set.

## Validation

- Focused TypeScript package:

```bash
cd typescript/examples/retrieval_filtering/hr_policy_lookup
npm test
npm run typecheck
npm run build
```

- Fast repo TypeScript validation:

```bash
./scripts/validate_typescript_fast.sh
```
