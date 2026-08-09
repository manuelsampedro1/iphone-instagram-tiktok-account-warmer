"""Fail-closed compatibility shell for removed engagement actions."""
from __future__ import annotations

from .runner_build import RUNNER_BLOCK_REASON


class Engager:
    """Retain the old symbol while refusing before any action is attempted."""

    def __init__(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError(RUNNER_BLOCK_REASON)
