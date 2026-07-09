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

Start with [Python guide](python/README.md) or [TypeScript guide](typescript/README.md) if you want language-level orientation first.

Use the enforcement-point catalog below when you already know which runtime
behavior you want to inspect.

Both language tracks include generic examples. TypeScript also includes starter
apps. Python also includes reference integrations.

## Ecosystem map

| Project | Question |
| --- | --- |
| [context-compiler (Python)](https://github.com/rlippmann/context-compiler), [context-compiler (TypeScript)](https://github.com/rlippmann/context-compiler-ts) | What is the authority contract? |
| [context-compiler-directive-drafter (Python)](https://github.com/rlippmann/context-compiler-directive-drafter), [context-compiler-directive-drafter (TypeScript)](https://github.com/rlippmann/context-compiler-directive-drafter-ts) | How is authority acquired? |
| [context-compiler-example-integrations](https://github.com/rlippmann/context-compiler-example-integrations) | Where can authority be enforced? |

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

## Organization

Examples are organized by enforcement point.

- Python includes generic examples and reference integrations.
- TypeScript includes generic examples and starter apps.
- Available examples differ between Python and TypeScript.

## Current layout

- [python/README.md](python/README.md) - Python examples and reference integrations
- [typescript/README.md](typescript/README.md) - TypeScript examples and starter apps

## Adding examples

Examples in this repo should:

- use explicit authoritative state
- avoid deriving Context Compiler state from model output
- remain meaningful with an adversarial stub
- demonstrate observable runtime behavior changes

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for more detail.

## Validation

Canonical repo-level validation commands:

```bash
uv sync --group dev --no-editable
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
