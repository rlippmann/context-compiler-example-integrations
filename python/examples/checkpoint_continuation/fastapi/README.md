# Checkpoint continuation with FastAPI

This example demonstrates checkpoint continuation across stateless HTTP request
boundaries.

## Enforcement point

Checkpoint continuation

## Domain

The domain is a small travel-booking change flow.

The first request initiates a change from `boston_trip` to `chicago_trip`.

That change requires confirmation before the host applies it.

## Runtime

This is a small FastAPI example.

FastAPI is secondary to the enforcement point.

It exists to show that the host can persist a checkpoint between separate HTTP
requests and restore it later into a fresh engine.

## Ownership boundary

Context Compiler owns:

- authoritative policy state
- pending continuation state
- checkpoint export and import

The host owns:

- checkpoint storage
- request routing
- booking mutation

In this example, the host creates a fresh engine per request.

The second request resumes the flow only because the host restores the saved
checkpoint, not because the process remembered a conversation.

## Why checkpoint continuation differs from state restore

Checkpoint continuation includes pending confirmation state.

Authoritative-state-only restore does not.

That difference matters here:

- restoring the full checkpoint lets a later `yes` resume the pending trip
  change
- restoring authoritative state alone does not resume that pending confirmation

## Why this is not prompt reinjection

This example does not re-send hidden instructions to a model.

The observable behavior change is host-side: the booking only changes after a
later request restores the checkpoint and confirmation succeeds.

## Endpoints

- `POST /change-trip`
  - creates a pending confirmation
  - persists a checkpoint in the host store
- `POST /confirm`
  - restores the saved checkpoint into a fresh engine
  - accepts `yes`, `no`, or unrelated text
  - applies the booking change only after successful confirmation
- `GET /booking`
  - returns the host-owned booking state

## Validate

From the repository root:

```bash
uv run pytest python/tests/test_fastapi_checkpoint_continuation_example.py
./scripts/validate_python.sh
```
