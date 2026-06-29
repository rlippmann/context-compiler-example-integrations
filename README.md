# Context Compiler Example Integrations

What runtime behavior changes when authoritative state exists?

These examples demonstrate how Context Compiler's authority contract can
influence runtime behavior across different AI pipeline stages.

Prompt reinjection influences model behavior.

Context Compiler influences runtime behavior.

Each example:
- demonstrates a single runtime enforcement point
- uses explicit authoritative state
- remains meaningful with an adversarial model stub
- focuses on the enforcement point rather than the framework

## Ecosystem map

| Repo | Question |
|---|---|
| context-compiler | What is the authority contract? |
| context-compiler-directive-drafter | How is authority acquired? |
| context-compiler-example-integrations | Where can authority be enforced? |

## Enforcement-point catalog

| Enforcement Point | Domain | Technology |
|---|---|---|
| Gateway middleware | Customer support routing | LiteLLM Proxy |
| Schema selection | Order / incident intake | Ollama |
| Checkpoint continuation | Travel booking | generic Python / TypeScript |
| Execution authorization | Expense approval | simple tool runner |
| Retrieval filtering | HR policy lookup | generic Python / TypeScript |
| Request construction / context assembly | Writing assistant | Open WebUI |
| Tool gating | Calendar / email / admin | MCP |

## How this repo is organized

Technology is secondary to enforcement point.

Examples are organized by enforcement point, not framework.

Python and TypeScript share the taxonomy. Implementations may differ by
language.

There is no parity requirement between Python and TypeScript examples.

Python examples may arrive before TypeScript examples.

TypeScript starter apps now split compiler-only and with-drafter variants.

## Repository boundaries

This repo is:
- an examples/integrations repo
- organized around runtime enforcement points
- not a library/package repo
- not the authority contract
- not the directive drafter
- not an acquisition-layer repo
- not a framework showcase

## Current layout

- [python/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/README.md)
- [typescript/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/README.md)

## Contribution expectations

Primary examples in this repo should:
- use explicit authoritative state
- avoid deriving Context Compiler state from model output
- remain meaningful with an adversarial stub
- demonstrate observable runtime behavior changes

See [CONTRIBUTING.md](/Users/rlippmann/Source/context-compiler-example-integrations/CONTRIBUTING.md) and [AGENTS.md](/Users/rlippmann/Source/context-compiler-example-integrations/AGENTS.md) for repository rules.

## Validation

Canonical repo-level validation commands:

```bash
uv sync --group dev
./scripts/validate_python.sh
./scripts/validate_typescript_fast.sh
./scripts/validate_typescript.sh
```

Python contributors may install and run local pre-commit hooks:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

TypeScript contributors can run the validation scripts directly without
installing Python pre-commit tooling.

CI is the authoritative cross-language validation path.

## License

Apache-2.0
