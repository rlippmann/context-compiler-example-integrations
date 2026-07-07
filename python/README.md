# Python examples

This package publishes Python example integrations organized by enforcement
point first.

Use it when you want concrete Python examples that show how authoritative
Context Compiler state changes runtime behavior in a host application.

The core library lives in
[`context-compiler`](https://github.com/rlippmann/context-compiler).
Directive recognition can be added with
[`context-compiler-directive-drafter`](https://github.com/rlippmann/context-compiler-directive-drafter),
but that layer is optional. This package is the examples and integration
patterns layer.

`context-compiler` defines the authority contract.
`context-compiler-directive-drafter` can optionally help acquire and draft
authority, but it is not the authority layer.
This examples package shows where authority is enforced.

Prompt reinjection influences model behavior.
Context Compiler influences runtime behavior.

## Start here

Start with a generic example README below if you want the clearest explanation
of one enforcement point before looking at runtime-specific integrations.

## Generic examples

These generic examples are the main starting point for new readers.

Open the enforcement point that matches the runtime behavior you want to
inspect:

- [Checkpoint continuation](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/checkpoint_continuation/README.md): persisted confirmation and resume flows change host behavior across turns or requests
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

- [python/reference_integrations/litellm_proxy/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/litellm_proxy/README.md)
- [python/reference_integrations/openwebui_pipe/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/openwebui_pipe/README.md)

## Run an example

These published package docs are for discovery.

To explore or run an example, use a repository checkout:

1. Clone
   [`context-compiler-example-integrations`](https://github.com/rlippmann/context-compiler-example-integrations).
2. Choose a generic example or a reference integration.
3. Open that example's README.
4. Follow the example-specific setup, runtime, and validation instructions.
