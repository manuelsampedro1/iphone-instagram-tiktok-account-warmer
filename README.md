# AutoWarmer 1.0.0, diagnostic safety fork

This is an unofficial diagnostic adaptation of the published AutoWarmer 1.0.0
source. It can verify one pinned Mac helper and report a redacted model and iOS
version for connected iPhones.

It cannot control Instagram or TikTok, accept account or proxy data, sign
Apple code, provision devices, install software on an iPhone, or run the
original account automation. Those paths fail closed.

## Important limitation

The author's 1.0.0 release contains source code, not an iPhone application.
There is no `.app` or `.ipa` to install. It also omits the custom runner source
required by its original control code. Installing the stock upstream runner
would not make the release functional.

This repository therefore provides a Mac-side USB diagnosis only. A passing
diagnosis confirms the number, model, and iOS version of connected devices. It
does not claim that AutoWarmer was installed on either phone.

## Safe commands

From this directory:

```bash
python3 -m autowarmer doctor
python3 -m autowarmer diagnose
python3 -m autowarmer serve
python3 -m autowarmer serve --open
python3 tests/test_autowarmer.py
```

`diagnose` also accepts optional `--expect-count` and `--model` gates when an
operator wants to enforce an expected inventory without publishing that local
inventory in this repository.

Running the module without a command prints help and makes no device request.
The local web page binds to `127.0.0.1` and does not open a browser unless
`--open` is supplied.

Before every diagnosis, the helper must match the pinned extracted-binary
SHA-256, have an executable regular-file mode, and report go-ios 1.2.1. If
`bin/ios` is absent, this command downloads the exact pinned release, checks
the archive hash, extracted-binary hash, and version, then replaces the local
helper atomically:

```bash
python3 -m autowarmer install ios
```

That install command changes files on the Mac and requires network access. It
does not install anything on an iPhone.

## Privacy boundary

The public CLI and web page do not accept device identifiers, account handles,
proxies, Apple keys, or social login data. Diagnostic output omits device names
and identifiers, including on errors. Legacy automation commands are not
registered; the argument parser rejects them without invoking a command
handler.

Any operator inventory must remain outside this repository. It is ignored by
Git and is never loaded by this build.

## Provenance

This copy derives from:

- Repository: `Tej-Sharma/iphone-instagram-tiktok-account-warmer`
- Tag: `v1.0.0`
- Commit: `5f4b8ec0ffdcb23ef37ba0f1b472b70db7dc1ff0`
- Published ZIP SHA-256: `cc268ab9d30fde05d5f3bd1df05fbeef2ed98956acc9faca13ca8594bc406b1f`

The published tag and commit are not cryptographically signed. The included
[Business Source License 1.1](LICENSE) states a change to Apache 2.0 on
2030-08-07. BSL 1.1 is source available during its restriction period, not an
OSI-approved open source license.
