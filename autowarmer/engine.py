"""Fail-closed compatibility shell for the unpublished driving engine.

The v1.0.0 archive contains social-app automation code, but its required
on-device WebDriverAgent routes were not published.  The public API remains
importable for compatibility while every entry point fails before it reads or
writes account state, opens an app, or contacts a phone.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .device import Config
from .runner_build import RUNNER_BLOCK_REASON


def _blocked() -> None:
    raise RuntimeError(RUNNER_BLOCK_REASON)


class Engine:
    """Compatibility facade with all planning and driving paths disabled."""

    def __init__(self, cfg: Config, state_root: Path):
        del cfg, state_root
        _blocked()

    def plan_all(self) -> List[object]:
        _blocked()

    def status(self) -> List[dict]:
        _blocked()

    def verify_account(self, username: str) -> dict:
        del username
        _blocked()

    def run_account(self, username: str, live: bool = False,
                    trace_level: Optional[str] = None,
                    engage_live: bool = True, max_attempts: int = 2,
                    platform: Optional[str] = None) -> dict:
        del username, live, trace_level, engage_live, max_attempts, platform
        _blocked()

    def _teardown_lane(self) -> None:
        _blocked()

    def _drive(self, *args, **kwargs) -> dict:
        del args, kwargs
        _blocked()

    @staticmethod
    def _comment_text(*args, **kwargs) -> str:
        del args, kwargs
        _blocked()

    @staticmethod
    def _pick_comment(*args, **kwargs) -> str:
        del args, kwargs
        _blocked()
