"""Acceptance tests for the diagnostic-only AutoWarmer safety build."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autowarmer import __main__ as cli  # noqa: E402
from autowarmer import app, diagnostics, fleet, install_tools, runner_build  # noqa: E402
from autowarmer.apps import AppFlow  # noqa: E402
from autowarmer.device import Config, Driver, GoIos, WDA  # noqa: E402
from autowarmer.engage import Engager  # noqa: E402
from autowarmer.engine import Engine  # noqa: E402
from tools import make_zip  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def zip_with_ios(payload: bytes = b"verified-go-ios") -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ios", payload)
    return out.getvalue()


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.verify = mock.patch.object(
            diagnostics, "_verified_binary", side_effect=lambda path: path)
        self.verify.start()
        self.addCleanup(self.verify.stop)

    def test_happy_path_is_redacted_and_uses_only_list_and_info(self):
        ids = ("a" * 40, "b" * 40)
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv[-1] == "list":
                body = {"deviceList": list(ids)}
            else:
                body = {
                    "DeviceName": "Private owner name",
                    "ProductType": "iPhone12,1",
                    "ProductVersion": "26.4.2",
                    "UniqueDeviceID": argv[-1],
                }
            return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")

        with mock.patch.object(diagnostics.subprocess, "run", side_effect=fake_run):
            rows = diagnostics.inspect_devices("/verified/ios", 2, "iPhone12,1")

        self.assertEqual(rows, [
            {"slot": 1, "model": "iPhone12,1", "ios": "26.4.2"},
            {"slot": 2, "model": "iPhone12,1", "ios": "26.4.2"},
        ])
        self.assertEqual([item[0] for item in calls], [
            ["/verified/ios", "list"],
            ["/verified/ios", "info", "--udid", ids[0]],
            ["/verified/ios", "info", "--udid", ids[1]],
        ])
        serialized = json.dumps(rows)
        self.assertNotIn(ids[0], serialized)
        self.assertNotIn(ids[1], serialized)
        self.assertNotIn("Private owner name", serialized)
        self.assertTrue(all(call[1]["capture_output"] for call in calls))
        self.assertTrue(all(call[1]["timeout"] == 20 for call in calls))

    def test_count_gate_stops_before_device_info(self):
        result = subprocess.CompletedProcess([], 0,
                                             json.dumps({"deviceList": ["a" * 40]}), "")
        with mock.patch.object(diagnostics.subprocess, "run", return_value=result) as run:
            with self.assertRaisesRegex(diagnostics.DiagnosticError,
                                        "expected 2 connected iPhones, found 1"):
                diagnostics.inspect_devices("/verified/ios", 2, "iPhone12,1")
        self.assertEqual(run.call_count, 1)

    def test_duplicate_device_is_rejected(self):
        udid = "a" * 40
        result = subprocess.CompletedProcess([], 0,
                                             json.dumps({"deviceList": [udid, udid]}), "")
        with mock.patch.object(diagnostics.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(diagnostics.DiagnosticError, "duplicate"):
                diagnostics.inspect_devices("/verified/ios")

    def test_tool_error_never_echoes_private_output(self):
        private = "Private Name " + "a" * 40 + " /Users/private/path"
        result = subprocess.CompletedProcess([], 9, private, private)
        with mock.patch.object(diagnostics.subprocess, "run", return_value=result):
            with self.assertRaises(diagnostics.DiagnosticError) as caught:
                diagnostics.inspect_devices("/verified/ios")
        message = str(caught.exception)
        self.assertEqual(message, "device list failed with exit 9")
        self.assertNotIn("Private", message)
        self.assertNotIn("/Users", message)

    def test_start_failure_never_echoes_executable_path(self):
        with mock.patch.object(diagnostics.subprocess, "run",
                               side_effect=OSError("/private/evil")):
            with self.assertRaises(diagnostics.DiagnosticError) as caught:
                diagnostics.inspect_devices("/private/evil")
        self.assertEqual(str(caught.exception), "device list could not start")

    def test_model_and_required_fields_are_enforced(self):
        listing = subprocess.CompletedProcess([], 0,
                                              json.dumps({"deviceList": ["a" * 40]}), "")
        wrong = subprocess.CompletedProcess([], 0,
                                            json.dumps({"ProductType": "iPhone15,2",
                                                        "ProductVersion": "26.4"}), "")
        with mock.patch.object(diagnostics.subprocess, "run",
                               side_effect=[listing, wrong]):
            with self.assertRaisesRegex(diagnostics.DiagnosticError,
                                        "unexpected model iPhone15,2"):
                diagnostics.inspect_devices("/verified/ios", 1, "iPhone12,1")


class BinaryIntegrityTests(unittest.TestCase):
    def test_verified_helper_requires_hash_execute_bit_and_version(self):
        payload = b"pinned-helper"
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "ios"
            binary.write_bytes(payload)
            binary.chmod(0o755)
            version = subprocess.CompletedProcess(
                [], 0, '{"version":"1.2.1"}', "")
            with mock.patch.object(
                    diagnostics, "GO_IOS_BINARY_SHA256",
                    hashlib.sha256(payload).hexdigest()), \
                    mock.patch.object(diagnostics.subprocess, "run",
                                      return_value=version) as run:
                self.assertEqual(diagnostics._verified_binary(str(binary)),
                                 str(binary))
        run.assert_called_once_with(
            [str(binary), "version"], capture_output=True, text=True, timeout=20)

    def test_hash_mismatch_fails_before_helper_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "ios"
            binary.write_bytes(b"unexpected")
            binary.chmod(0o755)
            with mock.patch.object(diagnostics.subprocess, "run") as run:
                with self.assertRaisesRegex(diagnostics.DiagnosticError, "SHA-256"):
                    diagnostics._verified_binary(str(binary))
        run.assert_not_called()


class ControlGateTests(unittest.TestCase):
    def assert_blocked(self, callback):
        with self.assertRaisesRegex(RuntimeError, "runner installation.*disabled"):
            callback()

    def test_every_legacy_control_constructor_fails_closed(self):
        self.assert_blocked(lambda: Config(udid="secret"))
        self.assert_blocked(lambda: GoIos(object()))
        self.assert_blocked(lambda: WDA(8100))
        self.assert_blocked(lambda: Driver(object()))
        self.assert_blocked(lambda: AppFlow("instagram", object(), object()))
        self.assert_blocked(lambda: Engager("tiktok", object(), object()))
        self.assert_blocked(lambda: Engine(object(), ROOT / "state"))

    def test_fleet_entry_points_fail_before_file_or_device_access(self):
        self.assert_blocked(lambda: fleet.connected_udids(object()))
        self.assert_blocked(lambda: fleet.warm_all("/does/not/exist", ROOT / "state"))
        self.assert_blocked(lambda: fleet.status("/does/not/exist"))
        self.assert_blocked(lambda: fleet.onboard("/does/not/exist", "secret"))

    def test_runner_stub_does_not_read_signing_configuration(self):
        class Trap:
            def __getattribute__(self, name):
                raise AssertionError(f"configuration was read: {name}")

        logs = []
        result = runner_build.install_runner(Trap(), "secret", ROOT, logs.append)
        self.assertFalse(result["ok"])
        self.assertEqual(logs, [runner_build.RUNNER_BLOCK_REASON])


class CliTests(unittest.TestCase):
    def test_diagnose_uses_only_the_fixed_project_binary(self):
        with mock.patch.object(diagnostics, "inspect_devices", return_value=[]) as inspect:
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["diagnose", "--expect-count", "2", "--model", "iPhone12,1"])
        inspect.assert_called_once_with(str(ROOT / "bin" / "ios"), 2, "iPhone12,1")

    def test_caller_cannot_supply_an_executable_path(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(["diagnose", "--ios-binary", "/tmp/other"])
        self.assertEqual(caught.exception.code, 2)

    def test_all_old_mutating_verbs_are_unregistered(self):
        cases = (["status"], ["warm", "someone", "--live"],
                 ["warm-all"], ["onboard", "secret-device"])
        for argv in cases:
            error = io.StringIO()
            with self.subTest(argv=argv), contextlib.redirect_stderr(error):
                with self.assertRaises(SystemExit) as caught:
                    cli.main(argv)
                self.assertEqual(caught.exception.code, 2)
            self.assertNotIn("someone", error.getvalue())
            self.assertNotIn("secret-device", error.getvalue())

    def test_no_arguments_prints_help_without_starting_server(self):
        output = io.StringIO()
        with mock.patch.object(cli, "cmd_serve") as serve, \
                contextlib.redirect_stdout(output):
            cli.main([])
        serve.assert_not_called()
        self.assertIn("diagnostic-only safety build", output.getvalue())

    def test_removed_installer_targets_are_rejected_by_parser(self):
        for target in ("all", "pymobiledevice3", "vision_ocr"):
            with self.subTest(target=target), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    cli.main(["install", target])
                self.assertEqual(caught.exception.code, 2)


class InstallerTests(unittest.TestCase):
    def test_hash_failure_preserves_existing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            old = dest / "ios"
            old.write_bytes(b"working-old")
            old.chmod(0o755)
            with mock.patch.object(install_tools.urllib.request, "urlopen",
                                   return_value=FakeResponse(b"not-the-release")):
                result = install_tools.install_go_ios(dest, lambda _: None)
            self.assertFalse(result["ok"])
            self.assertEqual(old.read_bytes(), b"working-old")

    def test_version_failure_preserves_existing_binary(self):
        archive = zip_with_ios()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            old = dest / "ios"
            old.write_bytes(b"working-old")
            old.chmod(0o755)
            with mock.patch.object(install_tools, "GO_IOS_SHA256",
                                   hashlib.sha256(archive).hexdigest()), \
                    mock.patch.object(install_tools, "GO_IOS_BINARY_SHA256",
                                      hashlib.sha256(b"verified-go-ios").hexdigest()), \
                    mock.patch.object(install_tools.urllib.request, "urlopen",
                                      return_value=FakeResponse(archive)), \
                    mock.patch.object(install_tools.subprocess, "run",
                                      return_value=subprocess.CompletedProcess(
                                          [], 0, '{"version":"9.9.9"}', "")):
                result = install_tools.install_go_ios(dest, lambda _: None)
            self.assertFalse(result["ok"])
            self.assertEqual(old.read_bytes(), b"working-old")

    def test_verified_candidate_replaces_atomically_after_version_check(self):
        payload = b"new-verified-binary"
        archive = zip_with_ios(payload)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            old = dest / "ios"
            old.write_bytes(b"working-old")
            old.chmod(0o755)

            def fake_run(argv, **kwargs):
                if argv[0] == "xattr":
                    return subprocess.CompletedProcess(argv, 0, "", "")
                return subprocess.CompletedProcess(argv, 0,
                                                   '{"version":"1.2.1"}', "")

            with mock.patch.object(install_tools, "GO_IOS_SHA256",
                                   hashlib.sha256(archive).hexdigest()), \
                    mock.patch.object(install_tools, "GO_IOS_BINARY_SHA256",
                                      hashlib.sha256(payload).hexdigest()), \
                    mock.patch.object(install_tools.urllib.request, "urlopen",
                                      return_value=FakeResponse(archive)), \
                    mock.patch.object(install_tools.subprocess, "run",
                                      side_effect=fake_run) as run:
                result = install_tools.install_go_ios(dest, lambda _: None)
            self.assertTrue(result["ok"])
            self.assertEqual(old.read_bytes(), payload)
            self.assertEqual(stat.S_IMODE(old.stat().st_mode), 0o755)
            self.assertEqual(list(dest.glob(".ios-*.candidate")), [])
            xattr = next(call for call in run.call_args_list
                         if call.args[0][0] == "xattr")
            self.assertEqual(xattr.kwargs["timeout"], 10)

    def test_download_size_limit_preserves_existing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            old = dest / "ios"
            old.write_bytes(b"working-old")
            with mock.patch.object(install_tools, "MAX_GO_IOS_BYTES", 3), \
                    mock.patch.object(install_tools.urllib.request, "urlopen",
                                      return_value=FakeResponse(b"1234")):
                result = install_tools.install_go_ios(dest, lambda _: None)
            self.assertFalse(result["ok"])
            self.assertEqual(old.read_bytes(), b"working-old")

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def read_json(self, path):
        with urllib.request.urlopen(self.base + path, timeout=3) as response:
            return response.status, json.loads(response.read())

    def test_state_is_redacted_and_diagnostic_only(self):
        with mock.patch("autowarmer.app.setup.detect_all", return_value=[{
            "name": "ios", "label": "go-ios", "found": True,
            "path": "/private/path", "source": "secret", "hint": "none",
        }]):
            code, body = self.read_json("/api/state")
        self.assertEqual(code, 200)
        self.assertTrue(body["control_disabled"])
        self.assertEqual(body["mode"], "diagnostic-only")
        serialized = json.dumps(body).lower()
        for forbidden in ("/private/path", "udid", "p8_path", "accounts", "proxies"):
            self.assertNotIn(forbidden, serialized)

    def test_old_device_and_job_endpoints_are_gone(self):
        for path in ("/api/devices", "/api/job"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.read_json(path)
                self.assertEqual(caught.exception.code, 410)

    def test_post_is_rejected_without_echoing_body(self):
        secret = b'{"p8":"PRIVATE-KEY","udid":"SECRET-DEVICE"}'
        request = urllib.request.Request(self.base + "/api/config", data=secret,
                                         method="POST")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 409)
        body = caught.exception.read().decode()
        self.assertNotIn("PRIVATE-KEY", body)
        self.assertNotIn("SECRET-DEVICE", body)

    def test_oversized_post_is_rejected_before_body_read(self):
        request = urllib.request.Request(self.base + "/api/config", data=b"x",
                                         method="POST",
                                         headers={"Content-Length": str(app.MAX_BODY_BYTES + 1)})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 413)


class StaticSurfaceTests(unittest.TestCase):
    def test_public_modules_have_no_signing_or_device_config_surface(self):
        setup_source = (ROOT / "autowarmer" / "setup_flow.py").read_text()
        app_source = (ROOT / "autowarmer" / "app.py").read_text()
        cli_source = (ROOT / "autowarmer" / "__main__.py").read_text()
        for forbidden in ("store_p8", "build_config", "list_devices"):
            self.assertNotIn(forbidden, setup_source)
            self.assertNotIn(forbidden, app_source)
        self.assertNotIn("--ios-binary", cli_source)
        self.assertNotIn("xcodebuild", (ROOT / "autowarmer" / "runner_build.py").read_text())
        self.assertNotIn("xattr -dr", (ROOT / "AutoWarmer.command").read_text())

    def test_distribution_excludes_private_and_legacy_configuration(self):
        readme = (ROOT / "README.md").read_text().lower()
        config = (ROOT / "config.example.json").read_text().lower()
        for forbidden in ("p8_path", "--live", "warm-all",
                          "pymobiledevice3", "vision_ocr"):
            self.assertNotIn(forbidden, readme)
        for forbidden in ("p8", "udid", "username", "password", "proxy_host"):
            self.assertNotIn(forbidden, config)
        self.assertEqual(
            ["autowarmer", "README.md", "LICENSE", "AutoWarmer.command"],
            make_zip.INCLUDE,
        )

    def test_built_archive_contains_only_the_public_diagnostic_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "autowarmer").mkdir()
            (root / "autowarmer" / "__init__.py").write_text("safe = True\n")
            (root / "README.md").write_text("diagnostic only\n")
            (root / "LICENSE").write_text("license\n")
            launcher = root / "AutoWarmer.command"
            launcher.write_text("#!/bin/sh\n")
            launcher.chmod(0o755)
            (root / "private").mkdir()
            (root / "private" / "inventory.json").write_text("secret\n")
            (root / "bin").mkdir()
            (root / "bin" / "ios").write_bytes(b"helper")
            (root / "config.example.json").write_text("legacy\n")

            with mock.patch.object(make_zip, "ROOT", root), \
                    mock.patch.object(sys, "argv", ["make_zip.py", "test"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                make_zip.main()

            with zipfile.ZipFile(root / "dist" / "AutoWarmer-test.zip") as archive:
                names = set(archive.namelist())
                mode = archive.getinfo(
                    "AutoWarmer-test/AutoWarmer.command").external_attr >> 16
            self.assertEqual(names, {
                "AutoWarmer-test/autowarmer/__init__.py",
                "AutoWarmer-test/README.md",
                "AutoWarmer-test/LICENSE",
                "AutoWarmer-test/AutoWarmer.command",
            })
            self.assertEqual(stat.S_IMODE(mode), 0o755)

    def test_web_server_does_not_open_browser_by_default(self):
        import inspect
        default = inspect.signature(app.serve).parameters["open_browser"].default
        self.assertIs(default, False)

    def test_public_ui_has_no_mutating_controls(self):
        source = (ROOT / "autowarmer" / "ui.html").read_text().lower()
        for forbidden in ("type=\"file\"", "p8", "api/config", "api/devices",
                          "warm-all", "onboard", "install runner"):
            self.assertNotIn(forbidden, source)
        self.assertIn("phone control is disabled", source)

    def test_legacy_modules_have_no_executable_control_implementation(self):
        legacy = (
            "ai.py", "apps.py", "device.py", "engage.py", "engine.py",
            "fleet.py", "humanize.py", "incubation.py", "jobs.py",
            "perceive.py", "schedule.py", "screens.py", "trace.py",
            "vision.py",
        )
        forbidden = (
            "subprocess", "urllib", "xcodebuild", "xcuitest", "/wda/",
            "com.burbn.instagram", "com.zhiliaoapp.musically",
            ".screenshot(", ".tap(", ".swipe(", "launch_app(",
            "terminate_app(", "popen(", "urlopen(",
        )
        for name in legacy:
            source = (ROOT / "autowarmer" / name).read_text().lower()
            with self.subTest(module=name):
                for fragment in forbidden:
                    self.assertNotIn(fragment, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
