"""Fail-closed fleet compatibility API.

Device discovery for this safety build lives exclusively in diagnostics.py.
It returns redacted model and iOS facts and has no account or app access.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .runner_build import RUNNER_BLOCK_REASON


def _blocked() -> None:
    raise RuntimeError(RUNNER_BLOCK_REASON)


def connected_udids(cfg) -> set:
    del cfg
    _blocked()


def warm_all(config_path: str, state_root: Path, live: bool = True,
             engage_live: bool = True, only_udid: Optional[str] = None,
             rng=None) -> List[dict]:
    del config_path, state_root, live, engage_live, only_udid, rng
    _blocked()


def status(config_path: str) -> List[dict]:
    del config_path
    _blocked()


def onboard(config_path: str, udid: str) -> dict:
    del config_path, udid
    _blocked()
