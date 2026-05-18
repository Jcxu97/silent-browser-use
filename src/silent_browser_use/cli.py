"""Command-line entry point for silent-browser-use.

Exposes two console scripts (configured in pyproject.toml):

* `silent-browser-use` — the long form
* `sbu`                — short alias

Subcommands wrap the building blocks in `chrome_profile`, `login_flow`, and
`helpers` so a user can go from zero to a logged-in, persistent Chrome with
a single `sbu install`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, helpers
from .chrome_profile import ChromeProfile
from .login_flow import LoginFlow


def _die(msg: str, code: int = 1) -> None:
    print(f"[silent-browser-use] error: {msg}", file=sys.stderr)
    sys.exit(code)


# ---- subcommand implementations --------------------------------------

def cmd_install(args: argparse.Namespace) -> None:
    print("[1/4] Installing agent-browser CLI ...")
    helpers.install(with_deps=args.with_deps)
    profile = ChromeProfile()
    print(f"[2/4] Starting dedicated Chrome (profile={profile.profile_dir}) ...")
    profile.start()
    print("[3/4] Installing autostart entry ...")
    profile.install_autostart()
    print("[4/4] Connecting agent-browser to dedicated Chrome ...")
    helpers.connect(profile)
    print("[OK] silent-browser-use installed and ready.")


def cmd_login(args: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if not profile.is_running():
        profile.start()
    flow = LoginFlow(profile)
    ok = flow.request_login(args.site)
    if not ok:
        _die("login cancelled by user")
    print(f"[OK] Login flow for {args.site} complete; cookies persisted.")


def cmd_start(_: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if profile.is_running():
        print("[OK] Chrome already running.")
        return
    profile.start()
    print(f"[OK] Chrome started on port {profile.port}.")


def cmd_stop(_: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if not profile.is_running():
        print("[OK] Chrome was not running.")
        return
    profile.stop()
    print("[OK] Chrome stopped.")


def cmd_status(_: argparse.Namespace) -> None:
    profile = ChromeProfile()
    running = profile.is_running()
    print(f"profile dir   : {profile.profile_dir}")
    print(f"chrome binary : {profile._chrome_path}")
    print(f"debug port    : {profile.port}")
    print(f"chrome running: {'yes' if running else 'no'}")
    print(f"agent-browser : {'installed' if helpers.is_installed() else 'NOT installed'}")
    print(f"sbu version   : {__version__}")


def cmd_show(_: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if not profile.is_running():
        _die("Chrome is not running. Run `sbu start` first.")
    profile.show_window()
    print("[OK] window pulled on-screen.")


def cmd_hide(_: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if not profile.is_running():
        _die("Chrome is not running.")
    profile.hide_window()
    print("[OK] window pushed off-screen.")


def cmd_run(args: argparse.Namespace) -> None:
    profile = ChromeProfile()
    if not profile.is_running():
        profile.start()
    helpers.connect(profile)
    out = helpers.chat(args.instruction)
    if out:
        print(out)


def cmd_uninstall(_: argparse.Namespace) -> None:
    import platform
    import os
    import shutil

    profile = ChromeProfile()
    if profile.is_running():
        print("[1/3] Stopping Chrome ...")
        profile.stop()
    else:
        print("[1/3] Chrome not running, skipping stop.")

    print(f"[2/3] Removing profile dir {profile.profile_dir} ...")
    if profile.profile_dir.exists():
        shutil.rmtree(profile.profile_dir, ignore_errors=True)

    print("[3/3] Removing autostart entry ...")
    sysname = platform.system()
    targets: list[Path] = []
    if sysname == "Windows":
        startup = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
        targets.append(startup / "silent-browser-use-chrome.bat")
    elif sysname == "Darwin":
        targets.append(Path.home() / "Library/LaunchAgents/com.silent-browser-use.chrome.plist")
    else:
        targets.append(Path.home() / ".config/systemd/user/silent-browser-use-chrome.service")
    for t in targets:
        try:
            if t.exists():
                t.unlink()
        except OSError as e:  # noqa: BLE001
            print(f"  warn: could not delete {t}: {e}", file=sys.stderr)

    print("[OK] silent-browser-use uninstalled.")
    print("Note: agent-browser CLI itself was NOT removed; uninstall it via npm/brew if desired.")


# ---- argparse wiring -------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sbu",
        description="silent-browser-use — persistent Chrome profile + auto-login on top of agent-browser.",
    )
    p.add_argument("--version", action="version", version=f"silent-browser-use {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    sp = sub.add_parser("install", help="install agent-browser, start dedicated Chrome, enable autostart")
    sp.add_argument("--with-deps", action="store_true", help="(Linux) also install system-level deps")
    sp.set_defaults(func=cmd_install)

    sp = sub.add_parser("login", help="pop the Chrome window so you can sign in to a site once")
    sp.add_argument("site", help="display name of the site (e.g. nexusmods.com)")
    sp.set_defaults(func=cmd_login)

    sub.add_parser("start", help="start dedicated Chrome").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop dedicated Chrome").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="show Chrome / agent-browser / profile status").set_defaults(func=cmd_status)
    sub.add_parser("show", help="pull the dedicated Chrome window on-screen").set_defaults(func=cmd_show)
    sub.add_parser("hide", help="push the dedicated Chrome window off-screen").set_defaults(func=cmd_hide)

    sp = sub.add_parser("run", help="forward an instruction to agent-browser chat (uses our profile)")
    sp.add_argument("instruction", help="natural-language instruction for agent-browser")
    sp.set_defaults(func=cmd_run)

    sub.add_parser("uninstall", help="stop Chrome, remove profile dir, remove autostart").set_defaults(
        func=cmd_uninstall
    )

    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        _die("interrupted", code=130)
    except Exception as e:  # noqa: BLE001 — top-level CLI handler
        _die(str(e))


if __name__ == "__main__":
    main()
