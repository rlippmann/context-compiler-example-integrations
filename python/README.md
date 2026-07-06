# Python examples

Python examples in this repo stay organized by enforcement point first.

Open this section when you want the smallest Python examples that show a
runtime behavior change from authoritative state.

Start with a generic example README below if you want the clearest explanation
of an enforcement point before looking at framework-specific integrations.

Current generic Python examples include:

- [python/examples/checkpoint_continuation/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/checkpoint_continuation/README.md)
- [python/examples/execution_authorization/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/execution_authorization/README.md)
- [python/examples/gateway_middleware/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/gateway_middleware/README.md)
- [python/examples/prompt_construction/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/prompt_construction/README.md)
- [python/examples/retrieval_filtering/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/retrieval_filtering/README.md)
- [python/examples/schema_selection/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/schema_selection/README.md)
- [python/examples/tool_gating/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/tool_gating/README.md)

These generic examples are the main starting point for new readers.

They are small, enforcement-point-first, and usually the fastest way to see
what changes at runtime when saved state changes.

## Reference integrations

Python also includes reference integrations for runtime-specific behavior after
the generic examples.

Open a reference integration when you want to see the same kind of runtime
behavior on a specific host or framework surface.

Start with the generic example first, then use the Python reference
integrations to inspect a runtime-specific path:

- [python/reference_integrations/litellm_proxy/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/reference_integrations/litellm_proxy/README.md)
- [python/reference_integrations/openwebui_pipe/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/reference_integrations/openwebui_pipe/README.md)

Choose Python when you want:

- generic examples with small host-side flows
- the current reference integrations in this repo
- runtime-specific behavior after you already understand the generic path
