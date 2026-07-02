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

## Commit and PR naming

- Use conventional prefixes in commit messages and PR titles when applicable.
- Prefer `feat:` for user-visible additions or behavior changes.
- Prefer `fix:` for bug fixes.
- Prefer `docs:` for documentation-only changes.
- Prefer `test:` for test-only changes.
- Prefer `refactor:` for internal restructures without user-visible behavior change.
- Prefer `chore:` for maintenance work.
- Keep commit messages and PR titles concise and behavior-oriented.
- When creating PRs with `gh`, use the repository PR template when one is available.
- Prefer a template-aware `gh pr create` flow over writing an ad hoc PR body.
- If a template is missing task-specific details, add them without dropping the template structure.

## Scope of changes

- Only modify files necessary for the requested task.
- Do not refactor unrelated code.
- Keep examples small and reviewable.
- If scope grows beyond one enforcement point, stop and ask for review.
- If an example needs a real framework, keep framework-specific code isolated.

## Validation

- Canonical Python validation: `./scripts/validate_python.sh`
- Fast TypeScript validation: `./scripts/validate_typescript_fast.sh`
- Canonical TypeScript validation: `./scripts/validate_typescript.sh`
- Python contributors may use local hooks: `uv run pre-commit run --all-files`
- Do not require TypeScript contributors to install or use Python pre-commit tooling for TypeScript validation.
- CI is the authoritative cross-language validation path.

## Example design requirements

All new examples should:

- Demonstrate one primary enforcement point.
- Use explicit authoritative Context Compiler state.
- Avoid model-derived state mutation.
- Avoid directive-drafter unless the example is specifically about acquisition-layer behavior.
- Include an adversarial stub or equivalent test where practical.
- Demonstrate observable runtime behavior change.
- Use natural domain vocabulary.
- Keep framework or runtime concerns secondary to the enforcement point.
- Include documentation.
- Include tests or smoke checks where practical.
- Prefer small runnable examples where practical.
- Prefer mocked or smoke validation over heavy live-runtime end-to-end flows.
- Make clear which component owns authoritative state and which component owns runtime behavior.
- When examples involve conflicting directives, preserve Context Compiler clarification semantics. Do not imply last-directive-wins behavior or host-side conflict resolution.

## Example completion requirements

Before considering an example complete:

- Run the repository validation path appropriate to the affected language or runtime.
- Ensure formatting, type checks, and tests or smoke checks pass.
- Report validation results when completing the task.

## Example self-review

Before reporting a task complete:

- Review the change against the example design requirements.
- Identify any unmet or partially satisfied requirements.
- Report them explicitly instead of silently accepting them.
- If the example depends on policy state, verify that contradiction/clarification behavior is covered where practical.

## Optional Components

When documenting optional packages or layers:

- Explain the standalone workflow first.
- Explain optional extensions second.
- Do not imply optional packages are required.

Examples should clearly distinguish:

- compiler-only usage
- optional directive-drafter usage
- optional framework integrations

## Documentation

This repository does not define the Context Compiler specification.

Within this repository, documentation that describes example behavior is
authoritative for the examples it documents.

Documentation is part of the project contract.

Documentation is not commentary.

README files, starter-app documentation, integration examples,
migration guides, and explicitly requested documentation changes are
part of the project contract.

Treat documentation requirements in a task as acceptance criteria.

README files, integration example docs, and explicitly requested documentation
changes are acceptance criteria.

Documentation examples explicitly referenced by a task are part of the
expected deliverable.

Do not treat documentation as merely illustrative unless explicitly stated.

Do not silently change documented behavior because implementation is easier.
Do not update documentation merely to match unintended behavior.
Do not weaken or remove user-facing tests to accommodate implementation.

If implementation, documentation, examples, tests, and task requirements
disagree:

1. Treat the documented repo purpose and task requirements as authoritative.
2. Report the mismatch.
3. Request review before changing documented behavior.
4. Do not resolve disagreements by silently changing docs.

## Example Migration

Before removing examples from another repository:

1. Verify an equivalent example exists here.
2. Verify the replacement preserves the user-visible behavior being taught.
3. Verify documentation points users to the replacement location.

Do not remove educational material solely because repository ownership changed.

## Documentation style

For README, integration, and package-listing docs, explain user-visible
behavior before architecture.

Prefer plain, concrete wording when accurate.

Prefer direct subjects and strong verbs.

Avoid noun stacks and passive phrasing when a simpler active sentence is
clearer.

Use simpler wording unless technical precision requires formal terminology.

Avoid describing features only in architectural terms when a behavior-first
explanation is possible.

When documenting guarantees or contracts, preserve precise language and do not
weaken behavioral commitments for readability.

Do not rewrite captured outputs or fixture-sensitive examples unless explicitly
asked.
