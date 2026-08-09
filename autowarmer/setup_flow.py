"""Read-only helper discovery for the diagnostic safety build.

The original setup wizard accepted phone, account, and Apple-signing data.
Those mutation surfaces are intentionally absent here. Device inspection uses
the verified project-local go-ios binary through diagnostics.py.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

APP_BIN = Path(__file__).resolve().parents[1] / "bin"


def find_go_ios() -> dict:
    """Report local availability for the CLI; the web API removes the path."""
    binary = APP_BIN / "ios"
    found = binary.is_file() and os.access(binary, os.X_OK)
    return {
        "name": "ios",
        "label": "go-ios",
        "found": found,
        "path": str(binary) if found else "",
        "source": "verified project copy" if found else "",
        "hint": "Run `python3 -m autowarmer install ios` from this folder.",
        "why": "reads the connected iPhone model and iOS version over USB",
        "installable": True,
    }


def detect_all() -> List[dict]:
    """Return the only helper used by diagnostic mode."""
    return [find_go_ios()]
