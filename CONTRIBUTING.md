# Contributing

Thanks for your interest in improving this project. Contributions are welcome.

## Workflow

Contributions are typically submitted via fork and pull request:

- fork the repository
- create a feature branch
- keep changes focused
- run the canonical validation checks
- open a pull request

## Validation

Run these commands before opening a pull request:

```bash
uv sync --group dev
./scripts/validate_python.sh
./scripts/validate_typescript_fast.sh
./scripts/validate_typescript.sh
npx --yes markdownlint-cli2
```

Python contributors may use `uv run pre-commit run --all-files` for the
lightweight local hook set.

TypeScript contributors can run `./scripts/validate_typescript_fast.sh` or
`./scripts/validate_typescript.sh` directly.

For a local Markdown-only check, run `npx --yes markdownlint-cli2`.

CI is the authoritative cross-language validation path.

## What belongs here

This repository demonstrates where authority can be enforced in runtime
systems.

Examples here should emphasize runtime behavior changes caused by explicit
authoritative state.

Examples here should not:

- act as acquisition-layer examples
- require directive-drafter for the primary example path
- depend on suggest-state behavior
- hide model-derived state mutation behind orchestration code
- only prove prompt compliance

## Example contribution checklist

- Demonstrates one primary runtime enforcement point
- Uses explicit authoritative state
- Does not derive Context Compiler state from model output
- Remains meaningful if the LLM is replaced with an adversarial stub
- Uses an adversarial stub that requests the action the active state should block or redirect
- Uses a domain distinct from adjacent examples
- Directive vocabulary feels natural in the chosen domain
- Domain is incidental; enforcement point is the purpose
- Runtime behavior changes are observable
- Framework is secondary to the enforcement point
- Example is understandable without knowledge of the underlying framework

## Design guidance

- Prefer small runnable examples
- Prefer mocked or smoke tests over heavy live-runtime end-to-end tests
- Keep one primary enforcement point per example
- If a realistic integration touches multiple concerns, identify the primary enforcement point clearly
- Keep framework-specific code isolated when a real framework is necessary

## Documentation requirements

Documentation is part of the project contract.

README files, integration examples, and explicitly requested documentation
changes are acceptance criteria when they are part of a task.

Do not silently change documented behavior because implementation is easier.
Do not update documentation merely to match unintended behavior.
Do not weaken or remove user-facing tests to accommodate implementation.

If implementation, documentation, examples, tests, and task requirements
disagree:

1. Treat the documented repo purpose and task requirements as authoritative.
2. Report the mismatch.
3. Request review before changing documented behavior.
4. Do not resolve disagreements by silently rewriting docs.

## Documentation style

For README, integration, and package-listing docs, explain user-visible
behavior before architecture.

Prefer plain, concrete wording when accurate. Favor direct subjects and strong
verbs over abstract or framework-heavy wording.

Avoid describing examples only in architectural terms when a behavior-first
explanation is possible.

Frameworks are implementation details. Enforcement points are primary.

## Scope of changes

- Keep pull requests focused
- Avoid unrelated refactors
- Do not migrate large bodies of existing example code unless explicitly requested
- Open an issue first for large structural changes
