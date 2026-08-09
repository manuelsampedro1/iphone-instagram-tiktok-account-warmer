"""Fail-closed compatibility shell for removed social-app flows."""
from __future__ import annotations

from .runner_build import RUNNER_BLOCK_REASON


class AppFlow:
    """Retain the old symbol while refusing before any app is contacted."""

    def __init__(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError(RUNNER_BLOCK_REASON)
