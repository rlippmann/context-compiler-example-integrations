# AGENTS.md

Guidelines for AI agents working in this repository.

## Repository boundary

This repo demonstrates where authority can be enforced.

It does not define the authority contract.

It does not acquire authority.

Do not add new Context Compiler core semantics.
Do not derive authoritative state from model output.

Examples should demonstrate runtime behavior changes, not model compliance.

Every example should remain meaningful if the LLM is replaced by an
adversarial stub.

Frameworks are implementation details. Enforcement points are primary.

Domains are teaching aids. Enforcement points are primary.

## Branch and git rules

- Do not commit, push, or open a PR unless explicitly instructed.
- Never commit directly to `main`.
- Never push directly to `main`.
- Never check out or modify `main`.
- If currently on `main`, stop and ask before making changes.
- Always work on a feature branch when a branch is needed.
- Do not perform history-rewriting operations unless explicitly instructed.

## Scope of changes

- Only modify files necessary for the requested task.
- Do not refactor unrelated code.
- Keep examples small and reviewable.
- If scope grows beyond one enforcement point, stop and ask for review.
- If an example needs a real framework, keep framework-specific code isolated.

## Example design rules

- Use explicit authoritative state.
- Do not derive Context Compiler state from model output.
- Avoid hidden model-derived state mutation.
- Keep one primary enforcement point per example.
- Make runtime behavior changes observable.
- Ensure every example remains meaningful with an adversarial stub.
- Prefer small runnable examples over broad framework demonstrations.
- Prefer mocked or smoke validation over heavy live-runtime end-to-end flows.
- Primary examples should not depend on directive-drafter.

## Documentation

Documentation is part of the project contract.

README files, integration example docs, and explicitly requested documentation
changes are acceptance criteria.

Do not silently change documented behavior because implementation is easier.
Do not update documentation merely to match unintended behavior.
Do not weaken or remove user-facing tests to accommodate implementation.

If implementation, documentation, examples, tests, and task requirements
disagree:

1. Treat the documented repo purpose and task requirements as authoritative.
2. Report the mismatch.
3. Request review before changing documented behavior.
4. Do not resolve disagreements by silently changing docs.

## Documentation style

For README, integration, and package-listing docs, explain user-visible
behavior before architecture.

Prefer plain, concrete wording when accurate.

Prefer direct subjects and strong verbs.

Avoid describing features only in architectural terms when a behavior-first
explanation is possible.
