# Request construction / context assembly

These examples show how a host assembles prompts from explicit authoritative
Context Compiler state before any model call would occur.

## Current examples

- [writing_assistant](./writing_assistant/README.md): generic TypeScript prompt
  construction for a writing assistant with no LLM call

## Example requirements

- Host owns prompt assembly.
- Context Compiler owns authoritative state.
- Examples must not derive state from model output.
- Examples must remain meaningful with an adversarial stub or no model call.
