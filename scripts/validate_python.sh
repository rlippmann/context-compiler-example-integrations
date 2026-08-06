#!/usr/bin/env bash

set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"

echo "Running ruff check..."
uv run --no-sync ruff check

echo "Running ruff format check..."
uv run --no-sync ruff format --check

echo "Running mypy..."
uv run --no-sync mypy

echo "Running pytest..."
uv run --no-sync pytest python/tests

echo "All Python checks passed."
