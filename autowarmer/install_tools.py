"""Install the single helper used by the diagnostic safety build.

The helper lands in this project. No sudo, PATH edits, Apple signing,
provisioning, phone installation, Python package installation, or Swift
compilation is performed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

GO_IOS_VERSION = "v1.2.1"
GO_IOS_URL = ("https://github.com/danielpaulus/go-ios/releases/download/"
              f"{GO_IOS_VERSION}/go-ios-mac.zip")
GO_IOS_SHA256 = "52acff5caa4b8ccb84cab0d44d988f3110a6773a43134281a899ae3c458c866c"
GO_IOS_BINARY_SHA256 = "b8a279520a875c62d281a7a9e23fe187401ab1c4af1eb328e329ce6e364d8611"
MAX_GO_IOS_BYTES = 128 * 1024 * 1024


# ------------------------------------------------------------------ go-ios


def install_go_ios(dest_dir: Path, log: Callable[[str], None] = print) -> dict:
    """Install a verified go-ios release without replacing a working copy
    until the candidate has passed its version check."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "ios"
    candidate: Path | None = None
    url = GO_IOS_URL
    log(f"  downloading {url}")
    try:
        with tempfile.TemporaryDirectory() as td:
            zip_path = Path(td) / "go-ios.zip"
            req = urllib.request.Request(url, headers={"User-Agent": "AutoWarmer"})
            with urllib.request.urlopen(req, timeout=300) as r, \
                    open(zip_path, "wb") as f:
                total = 0
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_GO_IOS_BYTES:
                        return {"ok": False, "path": "",
                                "error": "go-ios download exceeded the size limit"}
                    f.write(chunk)
            size = zip_path.stat().st_size
            digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            if digest != GO_IOS_SHA256:
                return {"ok": False, "path": "",
                        "error": ("go-ios download hash mismatch: expected "
                                  f"{GO_IOS_SHA256}, got {digest}")}
            log(f"  downloaded {size/1024/1024:.1f} MB, unpacking")
            with zipfile.ZipFile(zip_path) as z:
                try:
                    member = z.getinfo("ios")
                except KeyError:
                    return {"ok": False, "path": "",
                            "error": "that download did not contain an exact `ios` binary"}
                archived_mode = member.external_attr >> 16
                archived_type = stat.S_IFMT(archived_mode)
                if (member.is_dir() or archived_type == stat.S_IFLNK
                        or archived_type not in (0, stat.S_IFREG)
                        or member.file_size <= 0
                        or member.file_size > MAX_GO_IOS_BYTES):
                    return {"ok": False, "path": "",
                            "error": "the archived `ios` member is not a safe regular file"}
                fd, candidate_name = tempfile.mkstemp(
                    dir=dest_dir, prefix=".ios-", suffix=".candidate")
                candidate = Path(candidate_name)
                with z.open(member) as src, os.fdopen(fd, "wb") as out:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
            candidate.chmod(0o755)
            candidate_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if candidate_digest != GO_IOS_BINARY_SHA256:
                return {"ok": False, "path": "",
                        "error": ("extracted go-ios binary hash mismatch: expected "
                                  f"{GO_IOS_BINARY_SHA256}, got {candidate_digest}")}
            # The exact verified candidate is the only object whose quarantine
            # marker is removed. Never clear quarantine recursively.
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(candidate)],
                           capture_output=True, timeout=10)
            check = subprocess.run([str(candidate), "version"], capture_output=True,
                                   text=True, timeout=60)
            if check.returncode != 0:
                return {"ok": False, "path": "",
                        "error": "the verified go-ios candidate would not run"}
            try:
                reported = str(json.loads(check.stdout).get("version", ""))
            except (AttributeError, TypeError, json.JSONDecodeError):
                reported = ""
            if reported.lstrip("v") != GO_IOS_VERSION.lstrip("v"):
                return {"ok": False, "path": "",
                        "error": ("go-ios candidate version mismatch: expected "
                                  f"{GO_IOS_VERSION}, got {reported or 'unknown'}")}
            os.replace(candidate, dest)
            candidate = None
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "path": "",
                "error": f"download failed: {e}. You can install it by hand from "
                         "github.com/danielpaulus/go-ios/releases"}
    finally:
        if candidate is not None:
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
    log(f"  installed go-ios {GO_IOS_VERSION} at {dest}")
    return {"ok": True, "path": str(dest), "error": "", "version": GO_IOS_VERSION}


TOOLS = {
    "ios": ("go-ios", lambda root, log: install_go_ios(Path(root) / "bin", log)),
}


def install(tool: str, root: Path, log: Callable[[str], None] = print) -> dict:
    """Install the named diagnostic helper."""
    entry = TOOLS.get(tool)
    if entry is None:
        return {"ok": False, "path": "",
                "error": f"{tool} has to be installed by hand"}
    label, fn = entry
    log(f"installing {label}...")
    res = fn(root, log)
    log(("done: " + res["path"]) if res["ok"] else ("failed: " + res["error"]))
    return res
