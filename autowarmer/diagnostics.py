"""Strict, read-only checks for the connected iPhones.

This module verifies the pinned helper, then calls go-ios `version`, `list`,
and `info`. It does not install an app, start WebDriverAgent, take screenshots,
open social apps, or write state.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Optional

from .install_tools import GO_IOS_BINARY_SHA256, GO_IOS_VERSION


class DiagnosticError(RuntimeError):
    """The device inventory did not meet the requested acceptance gate."""


_DEVICE_ID_PATTERNS = (
    re.compile(r"(?i)\b[0-9a-f]{40}\b"),
    re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{16,32}\b"),
)


def _sanitize_detail(detail: object, redact: tuple[str, ...]) -> str:
    """Keep device identifiers out of diagnostic errors and reports."""
    clean = str(detail)
    for secret in redact:
        if secret:
            clean = clean.replace(secret, "[device-id-redacted]")
    for pattern in _DEVICE_ID_PATTERNS:
        clean = pattern.sub("[device-id-redacted]", clean)
    return clean


def _json_command(argv: list[str], label: str,
                  redact: tuple[str, ...] = ()) -> object:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise DiagnosticError(f"{label} timed out") from exc
    except OSError as exc:
        raise DiagnosticError(f"{label} could not start") from exc
    if result.returncode != 0:
        # Tool stderr can include a device name, identifier, or a local path.
        # Report only the exit status from this privacy-preserving command.
        raise DiagnosticError(f"{label} failed with exit {result.returncode}")
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"{label} returned invalid JSON") from exc


def _verified_binary(ios_binary: str) -> str:
    """Fail before execution unless the helper is the pinned regular file."""
    binary = os.path.expanduser(os.path.expandvars(ios_binary or ""))
    path = Path(binary)
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or not os.access(path, os.X_OK):
            raise DiagnosticError("diagnostic helper is not an executable regular file")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except DiagnosticError:
        raise
    except OSError as exc:
        raise DiagnosticError("diagnostic helper is unavailable") from exc
    if digest != GO_IOS_BINARY_SHA256:
        raise DiagnosticError("diagnostic helper failed its SHA-256 check")
    version = _json_command([binary, "version"], "helper version")
    if (not isinstance(version, dict)
            or str(version.get("version", "")).lstrip("v")
            != GO_IOS_VERSION.lstrip("v")):
        raise DiagnosticError("diagnostic helper reported an unexpected version")
    return binary


def inspect_devices(ios_binary: str, expect_count: Optional[int] = None,
                    expected_model: str = "") -> list[dict]:
    """Return only non-secret public facts after enforcing strict expectations."""
    binary = _verified_binary(ios_binary)
    listing = _json_command([binary, "list"], "device list")
    if not isinstance(listing, dict) or not isinstance(listing.get("deviceList"), list):
        raise DiagnosticError("device list has no valid deviceList array")
    udids = listing["deviceList"]
    if any(not isinstance(item, str) or not item.strip() for item in udids):
        raise DiagnosticError("device list contains an invalid device identifier")
    if len(set(udids)) != len(udids):
        raise DiagnosticError("device list contains a duplicate device")
    if expect_count is not None and len(udids) != expect_count:
        raise DiagnosticError(
            f"expected {expect_count} connected iPhones, found {len(udids)}")

    rows = []
    for index, udid in enumerate(udids, start=1):
        info = _json_command([binary, "info", "--udid", udid], "device info",
                             redact=(udid,))
        if not isinstance(info, dict):
            raise DiagnosticError("device info is not a JSON object")
        row = {
            "slot": index,
            "model": str(info.get("ProductType") or "").strip(),
            "ios": str(info.get("ProductVersion") or "").strip(),
        }
        missing = [key for key, value in row.items() if not value]
        if missing:
            raise DiagnosticError(
                "device info is incomplete: missing " + ", ".join(missing))
        if expected_model and row["model"] != expected_model:
            raise DiagnosticError(
                f"unexpected model {row['model']} in slot {index}, expected "
                f"{expected_model}")
        rows.append(row)
    return rows
