"""AutoWarmer diagnostic command line.

This safety build installs pinned Mac-side helpers and performs a strict,
redacted USB inventory.  Account planning, onboarding, runner installation,
and all phone control are disabled.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import APP_NAME, __version__

ROOT = Path(__file__).resolve().parents[1]


def cmd_serve(args) -> None:
    from .app import serve
    serve(port=args.port, open_browser=args.open_browser)


def cmd_doctor(args) -> None:
    del args
    from . import setup_flow as setup
    print(f"{APP_NAME} {__version__}")
    print("mode: diagnostic only\n")
    for item in setup.detect_all():
        mark = "ok" if item["found"] else "missing"
        print(f"{item['label']:<18} {mark}")
        if not item["found"]:
            print(f"  {item['hint']}")
    print("\nNo Apple signing key or account configuration is used by this build.")


def cmd_diagnose(args) -> None:
    from .diagnostics import DiagnosticError, inspect_devices
    try:
        devices = inspect_devices(str(ROOT / "bin" / "ios"),
                                  args.expect_count, args.model)
    except DiagnosticError as exc:
        print(f"diagnosis failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps({"ok": True, "count": len(devices), "devices": devices},
                     indent=2, ensure_ascii=False))


def cmd_install(args) -> None:
    from .install_tools import install
    result = install(args.tool, ROOT)
    if not result.get("ok"):
        print(result.get("error", "installation failed"), file=sys.stderr)
        raise SystemExit(1)


def main(argv=None) -> None:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="autowarmer", description=f"{APP_NAME}: diagnostic-only safety build")
    parser.add_argument("--version", action="version",
                        version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    serve_parser = sub.add_parser("serve", help="open the local diagnostic page")
    serve_parser.add_argument("--port", type=int, default=8790)
    serve_parser.add_argument("--open", action="store_true", dest="open_browser")
    serve_parser.set_defaults(fn=cmd_serve)

    sub.add_parser("doctor", help="check local helper availability").set_defaults(
        fn=cmd_doctor)

    diagnose = sub.add_parser("diagnose", help="strict redacted iPhone inventory")
    diagnose.add_argument("--expect-count", type=int)
    diagnose.add_argument("--model", default="")
    diagnose.set_defaults(fn=cmd_diagnose)

    install = sub.add_parser("install", help="install the pinned diagnostic helper")
    install.add_argument("tool", choices=["ios"])
    install.set_defaults(fn=cmd_install)

    if not raw_argv:
        parser.print_help()
        return
    args = parser.parse_args(raw_argv)
    args.fn(args)


if __name__ == "__main__":
    main()
