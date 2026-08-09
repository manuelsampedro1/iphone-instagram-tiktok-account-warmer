"""Fail-closed gate for the unpublished on-device runner.

AutoWarmer v1.0.0 calls two private WebDriverAgent routes, but the release does
not publish their implementation or an immutable source manifest. A stock or
locally supplied checkout must therefore never be compiled, signed, registered,
or installed by this build.
"""
from __future__ import annotations

from pathlib import Path

REQUIRED_WDA_ROUTES = ("/wda/mw/tap", "/wda/mw/swipe")
RUNNER_BLOCK_REASON = (
    "runner installation and live phone control are disabled for AutoWarmer "
    "v1.0.0 because the published release omits the WebDriverAgent "
    "implementation required by its private routes and provides no official "
    "immutable source manifest"
)


def install_runner(cfg: dict, udid: str, root: Path, log=print) -> dict:
    """Refuse before reading secrets, building, provisioning, or installing."""
    del cfg, udid, root
    log(RUNNER_BLOCK_REASON)
    return {"ok": False, "error": RUNNER_BLOCK_REASON}
