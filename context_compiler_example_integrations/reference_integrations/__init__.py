"""Reference integrations for installed and editable package use."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_SOURCE_DIR = _PACKAGE_DIR.parents[1] / "python" / "reference_integrations"

__path__ = [str(_PACKAGE_DIR)]
if _SOURCE_DIR.is_dir():
    __path__.append(str(_SOURCE_DIR))
