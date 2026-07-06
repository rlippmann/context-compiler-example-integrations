# Python examples

This package publishes Python example integrations organized by enforcement
point first.

Open this section when you want the smallest Python examples that show a
runtime behavior change from authoritative state.

Start with a generic example README below if you want the clearest explanation
of an enforcement point before looking at framework-specific integrations.

Current generic Python examples include:

- [python/examples/checkpoint_continuation/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/checkpoint_continuation/README.md)
- [python/examples/execution_authorization/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/execution_authorization/README.md)
- [python/examples/gateway_middleware/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/gateway_middleware/README.md)
- [python/examples/prompt_construction/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/prompt_construction/README.md)
- [python/examples/retrieval_filtering/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/retrieval_filtering/README.md)
- [python/examples/schema_selection/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/schema_selection/README.md)
- [python/examples/tool_gating/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/examples/tool_gating/README.md)

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

- [python/reference_integrations/litellm_proxy/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/litellm_proxy/README.md)
- [python/reference_integrations/openwebui_pipe/README.md](https://github.com/rlippmann/context-compiler-example-integrations/blob/main/python/reference_integrations/openwebui_pipe/README.md)

Choose Python when you want:

- generic examples with small host-side flows
- the current reference integrations in this repo
- runtime-specific behavior after you already understand the generic path
