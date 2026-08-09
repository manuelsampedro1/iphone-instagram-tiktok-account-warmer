"""Disabled legacy vision integration for the diagnostic-only build."""

from .runner_build import RUNNER_BLOCK_REASON


def __getattr__(name):
    del name
    raise RuntimeError(RUNNER_BLOCK_REASON)
