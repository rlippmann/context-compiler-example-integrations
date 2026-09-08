# Context Compiler Example Integrations

What runtime behavior changes when authoritative state exists?

These examples show how authoritative state changes application behavior at runtime.

Each example demonstrates a single enforcement point where premise and policy influence what a host allows, routes, retrieves, builds, or executes.

- The core authority contract is provided by [`context-compiler`](https://github.com/rlippmann/context-compiler).
- Directive recognition can optionally be added with [`context-compiler-directive-drafter`](https://github.com/rlippmann/context-compiler-directive-drafter).
- This repository focuses on where authoritative state changes runtime behavior.

*Prompt reinjection* influences ***model behavior***.

*Context Compiler* influences ***runtime behavior***.

Each example:

- demonstrates a single runtime enforcement point
- uses explicit authoritative state
- remains meaningful with an adversarial model stub
- focuses on the enforcement point rather than the framework

## Start here

Start with the [Python guide](python/README.md).

Use the enforcement-point catalog below when you already know which runtime
behavior you want to inspect.

Python includes generic examples and reference integrations.

## Ecosystem map

| Project | Question |
| --- | --- |
| [context-compiler](https://github.com/rlippmann/context-compiler) | What is the authority contract? |
| [context-compiler-directive-drafter](https://github.com/rlippmann/context-compiler-directive-drafter) | How is authority acquired? |
| [context-compiler-example-integrations](https://github.com/rlippmann/context-compiler-example-integrations) | Where can authority be enforced? |

## Enforcement-point catalog

| Enforcement Point | Domain | Technology |
| --- | --- | --- |
| [Gateway middleware](python/examples/gateway_middleware/README.md) | Customer support routing | Python, LiteLLM Proxy |
| [Schema selection](python/examples/schema_selection/README.md) | Order / incident intake | Python, Ollama, LiteLLM |
| [Checkpoint continuation](python/examples/checkpoint_continuation/README.md) | Travel booking | Python, FastAPI |
| [Execution authorization](python/examples/execution_authorization/README.md) | Expense approval | Python |
| [Retrieval filtering](python/examples/retrieval_filtering/README.md) | HR policy lookup | Python, ChromaDB |
| [Request construction / context assembly](python/examples/prompt_construction/README.md) | Writing assistant | Python, LiteLLM, Open WebUI |
| [Tool gating](python/examples/tool_gating/README.md) | Calendar / email / admin | Python, MCP |

## Organization

Examples are organized by enforcement point.

- Python includes generic examples and reference integrations.

## Current layout

- [python/README.md](python/README.md) - Python examples and reference integrations

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
uv run pre-commit run --all-files
npx --yes markdownlint-cli2
```

Python contributors may install and run local pre-commit hooks:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

CI runs Python validation through pre-commit and Markdown lint separately.

## License

Apache-2.0
