# Context Compiler Example Integrations for Python

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

- `context-compiler>=0.8.3`

Add extras only for the examples you want to inspect locally:

- `pip install "context-compiler-example-integrations[drafter]"` for examples that use `context-compiler-directive-drafter`
- `pip install "context-compiler-example-integrations[retrieval]"` for ChromaDB retrieval filtering examples
- `pip install "context-compiler-example-integrations[fastapi]"` for FastAPI variants
- `pip install "context-compiler-example-integrations[litellm]"` for LiteLLM-oriented examples and reference integrations
- `pip install "context-compiler-example-integrations[all]"` to install all package-managed optional dependencies

Open WebUI is not installed by this package. The Open WebUI reference
integration assumes Open WebUI is already installed and configured as the host
runtime.

## Generic examples

- [Checkpoint continuation](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/checkpoint_continuation/README.md): persisted authoritative state changes host behavior across turns or requests
- [Execution authorization](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/execution_authorization/README.md): protected host actions execute only when authoritative state allows them
- [Gateway middleware](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/gateway_middleware/README.md): the host allows, blocks, or routes requests before downstream work runs
- [Prompt construction](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/prompt_construction/README.md): the host builds different request or prompt payloads from authoritative state
- [Retrieval filtering](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/retrieval_filtering/README.md): the host changes which documents are eligible or relevant before returning results
- [Schema selection](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/schema_selection/README.md): the host picks different workflow or response schemas from authoritative state
- [Tool gating](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/tool_gating/README.md): the host changes which tools are visible or executable at runtime

## Reference integrations

Python also includes reference integrations for runtime-specific behavior after
the generic examples.

Open a reference integration when you want to see the same kind of runtime
behavior on a specific host or framework surface.

Start with the generic example first, then use the Python reference
integrations to inspect a runtime-specific path:

- [LiteLLM Proxy reference integration](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/litellm_proxy/README.md)
- [Open WebUI pipe reference integration](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/openwebui_pipe/README.md)

## Run an example

To explore or run an example, use a repository checkout:

1. Clone
   [`context-compiler-example-integrations`](https://github.com/rlippmann/context-compiler-example-integrations).
2. Choose a generic example or a reference integration.
3. Open that example's README.
4. Follow the example-specific setup, runtime, and validation instructions.
