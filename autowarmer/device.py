"""Fail-closed shell for the removed phone-control layer."""
from __future__ import annotations

from .runner_build import RUNNER_BLOCK_REASON


def _blocked(*args, **kwargs) -> None:
    del args, kwargs
    raise RuntimeError(RUNNER_BLOCK_REASON)


class Config:
    """Retain the old symbol but refuse to store device or account data."""

    def __init__(self, *args, **kwargs):
        _blocked(*args, **kwargs)


class GoIos:
    def __init__(self, *args, **kwargs):
        _blocked(*args, **kwargs)


class WDA:
    def __init__(self, *args, **kwargs):
        _blocked(*args, **kwargs)


class Driver:
    def __init__(self, *args, **kwargs):
        _blocked(*args, **kwargs)
