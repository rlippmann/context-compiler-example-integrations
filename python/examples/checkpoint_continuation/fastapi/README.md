# State Persistence with FastAPI

Saved authoritative compiler state lets later HTTP requests recover the same
policy decisions instead of starting over. This example shows state
persistence across stateless HTTP request boundaries.

## Enforcement Point

Authoritative state persistence

## Domain

The domain is a small travel-booking change flow.

The first request selects `chicago_trip` in compiler state. A later request
restores that saved state and lets the host apply the booking change.

## Runtime

This is a small FastAPI example.

FastAPI is secondary to the enforcement point.

It exists to show that the host can persist authoritative state between
separate HTTP requests and restore it later into a fresh engine.

## Ownership Boundary

Context Compiler owns:

- authoritative policy state
- state export through `export_json()`
- state restore through `import_json()`

The host owns:

- persisted state storage
- request routing
- booking mutation

In this example, the host creates a fresh engine per request.

The second request applies the saved itinerary only because the host restores
the persisted authoritative state, not because the process remembered a
conversation.

## Endpoints

- `POST /change-trip`
  - updates authoritative state with `use chicago_trip`
  - persists the resulting state JSON in the host store
- `POST /apply-trip`
  - restores the saved state JSON into a fresh engine
  - applies the booking change from restored policy state
- `GET /booking`
  - returns the host-owned booking state

## Validate

From the repository root:

```bash
uv run pytest python/tests/test_fastapi_checkpoint_continuation_example.py
./scripts/validate_python.sh
```
