"""Compatibility exports for the diagnostic-only safety build.

Phone discovery lives in diagnostics.py. The legacy engine export remains only
to fail closed for callers of the old API.
"""
from __future__ import annotations

from .device import Config
from .engine import Engine

__all__ = ["Config", "Engine"]
