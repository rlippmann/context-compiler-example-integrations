# Request construction / context assembly

These examples show how a host assembles prompts from explicit authoritative
Context Compiler state before any model call would occur.

## Current examples

- [writing_assistant](./writing_assistant/README.md): generic TypeScript prompt
  construction for a writing assistant with no LLM call

## Related integrations

These generic/examples-first docs teach the enforcement point.

Related concrete runtime surfaces:

- [typescript/starter_apps/nextjs/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/typescript/starter_apps/nextjs/README.md): TypeScript Next.js starter variants
- [python/examples/prompt_construction/litellm/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/examples/prompt_construction/litellm/README.md): Python LiteLLM-oriented prompt construction
- [python/reference_integrations/openwebui_pipe/README.md](/Users/rlippmann/Source/context-compiler-example-integrations/python/reference_integrations/openwebui_pipe/README.md): Python Open WebUI pipe integration

## Example requirements

- Host owns prompt assembly.
- Context Compiler owns authoritative state.
- Examples must not derive state from model output.
- Examples must remain meaningful with an adversarial stub or no model call.
