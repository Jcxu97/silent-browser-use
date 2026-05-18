"""silent-browser-use — companion toolkit for vercel-labs/agent-browser.

Adds:
- Persistent Chrome profile management (chrome_profile.py)
- Auto-login flow (login_flow.py)
- Pythonic helpers wrapping the agent-browser CLI (helpers.py)
- One-liner CLI: `silent-browser-use install / login / run` (cli.py)

Designed to be a thin layer ON TOP of agent-browser, not a fork. Upstream gets
all credit for the actual browser-automation engine; we add the chrome-profile
persistence and login UX missing from the default Chrome-for-Testing path.
"""

__version__ = "0.1.0"

from .chrome_profile import ChromeProfile
from .login_flow import LoginFlow, with_login_flow, detect_login_required
from .helpers import (
    # core
    open_url, click, fill, snapshot, screenshot,
    # mouse / keyboard
    dblclick, hover, focus, type_, press,
    keyboard_type, keyboard_inserttext,
    # selection / scroll
    select, check, uncheck, scroll, scroll_into_view, drag, upload,
    # inspection
    get_text, get_url, get_title, get_html, get_value, get_attr,
    get_count, get_box, get_styles, get_cdp_url,
    is_visible, is_enabled, is_checked,
    # semantic locators
    find_role, find_text, find_label, find_placeholder, find_alt,
    find_title, find_testid, find_first, find_last, find_nth,
    # waits / output / nl
    wait, pdf, evaluate, close, chat,
    # plumbing
    connect, install, is_installed, set_cdp_port, run,
)

__all__ = [
    "__version__",
    # connection
    "ChromeProfile", "connect", "set_cdp_port", "install", "is_installed",
    # login UX
    "LoginFlow", "with_login_flow", "detect_login_required",
    # core ops
    "open_url", "click", "fill", "snapshot", "screenshot",
    # mouse / keyboard
    "dblclick", "hover", "focus", "type_", "press",
    "keyboard_type", "keyboard_inserttext",
    # selection / scroll
    "select", "check", "uncheck", "scroll", "scroll_into_view", "drag", "upload",
    # inspection
    "get_text", "get_url", "get_title", "get_html", "get_value", "get_attr",
    "get_count", "get_box", "get_styles", "get_cdp_url",
    "is_visible", "is_enabled", "is_checked",
    # semantic locators
    "find_role", "find_text", "find_label", "find_placeholder", "find_alt",
    "find_title", "find_testid", "find_first", "find_last", "find_nth",
    # waits / output / nl / escape hatch
    "wait", "pdf", "evaluate", "close", "chat", "run",
]
