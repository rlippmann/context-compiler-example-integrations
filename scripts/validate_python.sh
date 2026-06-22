#!/usr/bin/env bash

set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"

uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync mypy
uv run --no-sync pytest python/tests
