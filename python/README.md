# Context Compiler Python Package

These examples show how authoritative state changes application behavior at runtime.

Each example demonstrates a single enforcement point where premise and policy influence what a host allows, routes, retrieves, builds, or executes.

- The core authority contract is provided by [`context-compiler`](https://github.com/rlippmann/context-compiler).
- Directive recognition can optionally be added with [`context-compiler-directive-drafter`](https://github.com/rlippmann/context-compiler-directive-drafter).
- These examples focus on where authoritative state changes application behavior.

*Prompt reinjection* influences ***model behavior***.

*Context Compiler* influences ***runtime behavior***.

## Install options

Base installation keeps this package discovery-first:

```shell
pip install "context-compiler-example-integrations"
```

That installs the shared core dependency only:

- `context-compiler>=0.9.1,<0.10`

Add extras only for the examples you want to inspect locally:

- `pip install "context-compiler-example-integrations[drafter]"` for examples that use `context-compiler-directive-drafter`
- `pip install "context-compiler-example-integrations[retrieval]"` for ChromaDB retrieval filtering examples
- `pip install "context-compiler-example-integrations[fastapi]"` for FastAPI variants
- `pip install "context-compiler-example-integrations[litellm]"` for LiteLLM-oriented examples and reference integrations
- `pip install "context-compiler-example-integrations[all]"` to install all package-managed optional dependencies

Open WebUI is not installed by this package. The Open WebUI reference
integration assumes Open WebUI is already installed and configured as the host
runtime.

## Package contents

The installed package exposes the Python examples and reference-integration
modules under `context_compiler_example_integrations`.

For the enforcement-point catalog and repository navigation, see the [root
README](../README.md). Each example and reference integration has its own
setup, runtime, and validation instructions.
