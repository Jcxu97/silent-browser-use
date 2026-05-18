"""Pythonic helpers wrapping the vercel-labs/agent-browser CLI.

Every function here shells out to the `agent-browser` binary via subprocess.
We do NOT reimplement browser-automation logic — agent-browser owns that.
This module just provides a friendlier Python surface so callers (and LLMs)
can do `from silent_browser_use.helpers import open_url, click, snapshot`
instead of constructing subprocess calls everywhere.

Pair with chrome_profile.ChromeProfile for persistent login: start the
profile, then call `connect(profile)` once so agent-browser attaches to our
dedicated Chrome on port 9222 instead of spawning Chrome-for-Testing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chrome_profile import ChromeProfile

DEFAULT_TIMEOUT = 60


def _agent_browser_bin() -> str:
    """Resolve the agent-browser binary path. On Windows, npm installs a .cmd shim."""
    import sys
    candidates = ["agent-browser.cmd", "agent-browser"] if sys.platform == "win32" else ["agent-browser"]
    for c in candidates:
        path = shutil.which(c)
        if path:
            return path
    return "agent-browser"  # let it fail with a clear error


AGENT_BROWSER_BIN = _agent_browser_bin()

# Module-level state: which CDP port should every command attach to?
# Set by `connect(profile)` or by env var SBU_CDP_PORT. When set, every
# `_run_ab` call prepends `--cdp <port>` so agent-browser uses our dedicated
# Chrome instead of spawning its own Chrome-for-Testing.
_active_cdp_port: int | None = None


def set_cdp_port(port: int | None) -> None:
    """Tell every subsequent agent-browser call to attach to this port. Pass None to clear."""
    global _active_cdp_port
    _active_cdp_port = port


def _resolve_cdp_port() -> int | None:
    if _active_cdp_port is not None:
        return _active_cdp_port
    env = os.environ.get("SBU_CDP_PORT")
    if env and env.isdigit():
        return int(env)
    return None


def _run_ab(*args: str, capture: bool = True, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run `agent-browser [--cdp <port>] <args>` and return stdout. Raise RuntimeError on failure."""
    if not is_installed():
        raise RuntimeError(
            "agent-browser not found on PATH. Run `sbu install` first "
            "(or `npm i -g @vercel/agent-browser`)."
        )
    # Prepend --cdp <port> if active, but skip for the `install` / `connect`
    # subcommands themselves (those don't take --cdp).
    cdp_port = _resolve_cdp_port()
    if cdp_port and args and args[0] not in ("install", "connect", "upgrade", "--version", "--help"):
        cmd = [AGENT_BROWSER_BIN, "--cdp", str(cdp_port), *args]
    else:
        cmd = [AGENT_BROWSER_BIN, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"agent-browser {' '.join(args)} timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "agent-browser binary disappeared between checks. Reinstall with `sbu install`."
        ) from e
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        raise RuntimeError(
            f"agent-browser {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"stderr: {stderr}\nstdout: {stdout}"
        )
    return (proc.stdout or "").strip()


# ---- install / connect ------------------------------------------------

def is_installed() -> bool:
    """Is the `agent-browser` CLI on PATH?"""
    import sys
    candidates = ["agent-browser.cmd", "agent-browser"] if sys.platform == "win32" else ["agent-browser"]
    return any(shutil.which(c) for c in candidates)


def install(with_deps: bool = False) -> None:
    """Run `agent-browser install` (optionally `--with-deps` on Linux)."""
    args = ["install"]
    if with_deps:
        args.append("--with-deps")
    _run_ab(*args, timeout=600)


def connect(profile: "ChromeProfile | None" = None) -> None:
    """Tell every subsequent helper call to attach agent-browser to this Chrome.

    With a ChromeProfile, uses its port; otherwise defaults to 9222. This
    sets a module-level flag — agent-browser actually receives `--cdp <port>`
    on each subsequent _run_ab call (no persistent daemon, every call is
    self-contained).
    """
    port = profile.port if profile is not None else 9222
    set_cdp_port(port)


# ---- navigation / interaction ----------------------------------------

def open_url(url: str) -> None:
    _run_ab("open", url)


def click(selector: str) -> None:
    _run_ab("click", selector)


def fill(selector: str, value: str) -> None:
    _run_ab("fill", selector, value)


def snapshot() -> str:
    """Return the accessibility-tree snapshot of the current page."""
    return _run_ab("snapshot")


def screenshot(path: str = "shot.png", full: bool = False) -> str:
    """Save a screenshot to `path`. Returns the path written."""
    args = ["screenshot", path]
    if full:
        args.append("--full")
    _run_ab(*args)
    return path


# ---- inspection -------------------------------------------------------

def get_text(selector: str) -> str:
    return _run_ab("get", "text", selector)


def get_url() -> str:
    return _run_ab("get", "url")


def get_title() -> str:
    return _run_ab("get", "title")


def find_role(role: str, action: str = "click", name: str | None = None) -> None:
    """`agent-browser find role <role> <action> [--name <name>]`."""
    args = ["find", "role", role, action]
    if name:
        args += ["--name", name]
    _run_ab(*args)


# ---- mouse / keyboard input ------------------------------------------

def dblclick(selector: str) -> None:
    _run_ab("dblclick", selector)


def hover(selector: str) -> None:
    _run_ab("hover", selector)


def focus(selector: str) -> None:
    _run_ab("focus", selector)


def type_(selector: str, text: str) -> None:
    """`agent-browser type <selector> <text>` — append text to input. (`type` is reserved in Python.)"""
    _run_ab("type", selector, text)


def press(key: str) -> None:
    """Press a single key or chord (e.g. 'Enter', 'Tab', 'Control+a')."""
    _run_ab("press", key)


def keyboard_type(text: str) -> None:
    """Type with real keystrokes into the currently-focused element (no selector)."""
    _run_ab("keyboard", "type", text)


def keyboard_inserttext(text: str) -> None:
    """Insert text without firing key events (faster, no IME quirks)."""
    _run_ab("keyboard", "inserttext", text)


def select(selector: str, value: str) -> None:
    _run_ab("select", selector, value)


def check(selector: str) -> None:
    _run_ab("check", selector)


def uncheck(selector: str) -> None:
    _run_ab("uncheck", selector)


def scroll(direction: str = "down", pixels: int | None = None, selector: str | None = None) -> None:
    """`agent-browser scroll <up|down|left|right> [px] [--selector <sel>]`."""
    args = ["scroll", direction]
    if pixels is not None:
        args.append(str(pixels))
    if selector:
        args += ["--selector", selector]
    _run_ab(*args)


def scroll_into_view(selector: str) -> None:
    _run_ab("scrollintoview", selector)


def drag(source: str, target: str) -> None:
    _run_ab("drag", source, target)


def upload(selector: str, *files: str) -> None:
    _run_ab("upload", selector, *files)


# ---- inspection (extended) -------------------------------------------

def get_html(selector: str) -> str:
    return _run_ab("get", "html", selector)


def get_value(selector: str) -> str:
    return _run_ab("get", "value", selector)


def get_attr(selector: str, attr: str) -> str:
    return _run_ab("get", "attr", selector, attr)


def get_count(selector: str) -> int:
    out = _run_ab("get", "count", selector)
    return int(out.strip()) if out.strip().isdigit() else 0


def get_box(selector: str) -> str:
    return _run_ab("get", "box", selector)


def get_styles(selector: str) -> str:
    return _run_ab("get", "styles", selector)


def get_cdp_url() -> str:
    return _run_ab("get", "cdp-url")


def is_visible(selector: str) -> bool:
    return _run_ab("is", "visible", selector).strip().lower() == "true"


def is_enabled(selector: str) -> bool:
    return _run_ab("is", "enabled", selector).strip().lower() == "true"


def is_checked(selector: str) -> bool:
    return _run_ab("is", "checked", selector).strip().lower() == "true"


# ---- semantic locators (find by ARIA / text / label / etc) -----------

def find_text(text: str, action: str = "click", exact: bool = False) -> None:
    args = ["find", "text", text, action]
    if exact:
        args.append("--exact")
    _run_ab(*args)


def find_label(label: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "label", label, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


def find_placeholder(placeholder: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "placeholder", placeholder, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


def find_alt(text: str, action: str = "click") -> None:
    _run_ab("find", "alt", text, action)


def find_title(text: str, action: str = "click") -> None:
    _run_ab("find", "title", text, action)


def find_testid(testid: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "testid", testid, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


def find_first(selector: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "first", selector, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


def find_last(selector: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "last", selector, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


def find_nth(n: int, selector: str, action: str = "click", value: str | None = None) -> None:
    args = ["find", "nth", str(n), selector, action]
    if value is not None:
        args.append(value)
    _run_ab(*args)


# ---- waits -----------------------------------------------------------

def wait(target: str | int, *, text: str | None = None, url: str | None = None,
         load: str | None = None, fn: str | None = None) -> None:
    """`agent-browser wait <selector|ms> [--text X | --url X | --load X | --fn X]`."""
    args = ["wait", str(target)]
    if text:    args += ["--text", text]
    if url:     args += ["--url", url]
    if load:    args += ["--load", load]
    if fn:      args += ["--fn", fn]
    _run_ab(*args, timeout=120)


# ---- output (PDF / eval / close) -------------------------------------

def pdf(path: str = "page.pdf") -> str:
    _run_ab("pdf", path)
    return path


def evaluate(js: str) -> str:
    """Run JavaScript in the page; returns stdout (stringified result)."""
    return _run_ab("eval", js)


def close(all_sessions: bool = False) -> None:
    args = ["close"]
    if all_sessions:
        args.append("--all")
    _run_ab(*args)


# ---- LLM-driven natural-language step --------------------------------

def chat(instruction: str) -> str:
    """Send a free-form instruction to agent-browser's chat mode."""
    return _run_ab("chat", instruction, timeout=300)


# ---- generic escape hatch (any agent-browser command we forgot) ------

def run(*args: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Pass-through to `agent-browser <args>`. Use for any command not
    covered by a typed helper above. Example::

        run("screenshot", "--annotate", "shots/labeled.png")
    """
    return _run_ab(*args, timeout=timeout)


if __name__ == "__main__":
    print(f"agent-browser installed: {is_installed()}")
    print(
        "Public API:",
        ", ".join(
            [
                "is_installed",
                "install",
                "connect",
                "open_url",
                "click",
                "fill",
                "snapshot",
                "screenshot",
                "get_text",
                "get_url",
                "get_title",
                "find_role",
                "chat",
            ]
        ),
    )
