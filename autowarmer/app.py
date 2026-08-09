"""Minimal localhost dashboard for diagnostic-only AutoWarmer.

The API exposes tool availability only.  It cannot accept a binary path,
store configuration or Apple keys, return device identifiers, or start a job.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from . import APP_NAME, __version__
from . import setup_flow as setup
from .runner_build import RUNNER_BLOCK_REASON

UI = Path(__file__).resolve().parent / "ui.html"
MAX_BODY_BYTES = 64 * 1024


def _tool_rows() -> list[dict]:
    """Return no executable paths or local source metadata."""
    return [{"name": item["name"], "label": item["label"],
             "found": bool(item["found"]), "hint": item["hint"]}
            for item in setup.detect_all()]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, payload) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        if path in ("/api/state", "/api/detect"):
            return self._json(200, {
                "app": APP_NAME,
                "version": __version__,
                "mode": "diagnostic-only",
                "tools": _tool_rows(),
                "phone_diagnostic": "available from the local command line",
                "control_disabled": True,
                "reason": RUNNER_BLOCK_REASON,
            })
        if path in ("/api/devices", "/api/job"):
            return self._json(410, {"error": "endpoint disabled in diagnostic mode"})
        return self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = MAX_BODY_BYTES + 1
        if size > MAX_BODY_BYTES:
            return self._json(413, {"error": "request too large"})
        if size:
            self.rfile.read(size)
        return self._json(409, {
            "error": "all mutations are disabled in diagnostic mode",
            "reason": RUNNER_BLOCK_REASON,
        })

    def log_message(self, *args) -> None:
        del args


def serve(config_path: Optional[str] = None, port: int = 8790,
          open_browser: bool = False) -> None:
    del config_path
    server = None
    for attempt in range(20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port + attempt), Handler)
            break
        except OSError:
            continue
    if server is None:
        print(f"could not find a free port near {port}")
        return
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"{APP_NAME} {__version__}: {url}")
    print("Diagnostic mode only. Press Ctrl-C to stop.")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
