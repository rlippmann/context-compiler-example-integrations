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

## Start here

Start with [python/README.md](python/README.md) or [typescript/README.md](typescript/README.md) if you want language-level orientation first.

Use the enforcement-point catalog below when you already know which runtime
behavior you want to inspect.

Both language tracks include generic examples. TypeScript also includes starter
apps. Python also includes reference integrations.

## Ecosystem map

| Repo | Question |
| --- | --- |
| context-compiler | What is the authority contract? |
| context-compiler-directive-drafter | How is authority acquired? |
| context-compiler-example-integrations | Where can authority be enforced? |

## Enforcement-point catalog

| Enforcement Point | Domain | Technology |
| --- | --- | --- |
| [Gateway middleware](python/examples/gateway_middleware/README.md) | Customer support routing | generic Python / TypeScript, LiteLLM Proxy |
| [Schema selection](python/examples/schema_selection/README.md) | Order / incident intake | generic Python / TypeScript, Ollama, LiteLLM, Vercel AI SDK |
| [Checkpoint continuation](python/examples/checkpoint_continuation/README.md) | Travel booking | generic Python / TypeScript, FastAPI, Node, Next.js |
| [Execution authorization](python/examples/execution_authorization/README.md) | Expense approval | generic Python / TypeScript, Node |
| [Retrieval filtering](python/examples/retrieval_filtering/README.md) | HR policy lookup | generic Python / TypeScript, ChromaDB |
| [Request construction / context assembly](python/examples/prompt_construction/README.md) | Writing assistant | generic Python / TypeScript, LiteLLM, Open WebUI, Next.js |
| [Tool gating](python/examples/tool_gating/README.md) | Calendar / email / admin | generic Python / TypeScript, MCP |

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
- not the core Context Compiler library package
- not the authority contract
- not the directive drafter
- not an acquisition-layer repo
- not a framework showcase

## Current layout

- [python/README.md](python/README.md)
- [typescript/README.md](typescript/README.md)

## Contribution expectations

Primary examples in this repo should:

- use explicit authoritative state
- avoid deriving Context Compiler state from model output
- remain meaningful with an adversarial stub
- demonstrate observable runtime behavior changes

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for repository rules.

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
