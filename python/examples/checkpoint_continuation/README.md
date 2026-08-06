# State Persistence

Persisting authoritative compiler state lets a fresh host process recover the
same premise and policy decisions without recreating them from model output or
conversation history. This example shows state persistence in a generic Python
travel-booking flow.

## Domain

The domain is a small travel-booking change flow.

The user selects a new itinerary, the compiler records that selection in
authoritative state, and the host later applies the booking change from a
restored engine.

## Runtime

This is a generic Python example.

It does not call an LLM.

It does not use directive drafter.

## What Context Compiler owns

Context Compiler owns:

- authoritative policy state
- serialization of that state through `export_json()`
- restoration of that state through `import_json()`

## What the host owns

The host owns:

- the booking record
- persisted state storage
- process boundaries
- the runtime behavior that actually applies the itinerary change

The host reads restored authoritative Context Compiler state and decides whether
to apply the booking change.

## Example behavior

1. The host starts with a booking on `boston_trip`.
2. The user selects `chicago_trip`.
3. Context Compiler updates authoritative state.
4. The host persists that state JSON.
5. A fresh host process restores the saved state into a new engine.
6. The host applies the booking change from the restored authoritative state.

## Run

From the repository root:

```bash
uv run python python/examples/checkpoint_continuation/example.py
uv run pytest python/tests/test_checkpoint_continuation_example.py
```

## FastAPI variant

For a request-boundary example, see
[python/examples/checkpoint_continuation/fastapi/README.md](fastapi/README.md).
