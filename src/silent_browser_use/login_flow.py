"""Auto-login UX flow for silent-browser-use.

When agent-browser hits a page that requires authentication, the user-facing
flow is: pop the dedicated Chrome window into view → tell the user to log in
manually → wait for confirmation → hide the window again. This keeps every
day usage silent (window off-screen) while still letting the human handle
captchas / 2FA / SSO when needed.

This module is purely UX glue: detection heuristics + a window-toggle context
manager. It does NOT itself drive the browser — chrome_profile owns Chrome
and helpers wraps the agent-browser CLI.
"""

from __future__ import annotations

import contextlib
import re
from typing import Callable

from .chrome_profile import ChromeProfile

_LOGIN_URL_RE = re.compile(r"/(login|signin|sign-in|auth|sso|account/login)\b", re.IGNORECASE)
_LOGIN_TEXT_HINTS = (
    "sign in",
    "log in",
    "log on",
    "登录",
    "登入",
    "登陆",
    "sign-in",
    "type=\"password\"",
    "type='password'",
    "input[type=password]",
)


def detect_login_required(snapshot_text: str, url: str) -> bool:
    """Heuristic: does the current page look like it needs the user to sign in?"""
    if url and _LOGIN_URL_RE.search(url):
        return True
    if not snapshot_text:
        return False
    lowered = snapshot_text.lower()
    return any(hint in lowered for hint in _LOGIN_TEXT_HINTS)


def _default_prompt(message: str) -> str:
    print(f"[silent-browser-use] {message}")
    return input("Press Enter when done (or type 'cancel' to abort): ").strip()


class LoginFlow:
    """Pop the browser, wait for the user, then hide it again."""

    def __init__(
        self,
        profile: ChromeProfile,
        prompt_user_fn: Callable[[str], str] | None = None,
    ):
        self.profile = profile
        self.prompt = prompt_user_fn or _default_prompt

    def request_login(self, site_name: str = "this site") -> bool:
        """Show window → wait for user → hide window. Returns True unless cancelled."""
        try:
            self.profile.show_window()
        except Exception as e:  # noqa: BLE001 — we want to surface but continue UX
            print(f"[silent-browser-use] Warning: could not show window ({e}); proceeding anyway.")
        try:
            reply = self.prompt(
                f"Please log in to {site_name} in the Chrome window that just appeared."
            )
        finally:
            try:
                self.profile.hide_window()
            except Exception as e:  # noqa: BLE001
                print(f"[silent-browser-use] Warning: could not hide window ({e}).")
        if reply and reply.lower() in {"cancel", "abort", "no", "n"}:
            return False
        return True

    # ---- context-manager form ----------------------------------------

    def __enter__(self) -> "LoginFlow":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Defensive: ensure the window is hidden on exit, even if request_login
        # was never called (e.g. login wasn't actually required).
        try:
            self.profile.hide_window()
        except Exception:  # noqa: BLE001
            pass


@contextlib.contextmanager
def with_login_flow(profile: ChromeProfile, site_name: str = "this site"):
    """Convenience wrapper.

    Usage::

        with with_login_flow(profile, "Nexus") as flow:
            if detect_login_required(snapshot(), get_url()):
                flow.request_login("Nexus")
    """
    flow = LoginFlow(profile)
    try:
        yield flow
    finally:
        try:
            profile.hide_window()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    # Smoke test: heuristic detection only — does not touch a real browser.
    cases = [
        ("https://nexusmods.com/users/login", "", True),
        ("https://example.com/", "Welcome! Sign in to continue", True),
        ("https://example.com/", "<input type=\"password\">", True),
        ("https://example.com/", "Hello world", False),
        ("https://baidu.com/", "请登录后继续", True),
    ]
    for url, snap, expected in cases:
        got = detect_login_required(snap, url)
        print(f"{'OK' if got == expected else 'FAIL'}  url={url!r:50s}  -> {got}")
