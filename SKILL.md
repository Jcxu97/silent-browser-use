---
name: silent-browser-use
description: Drive a DEDICATED hidden Chrome (port 9333) via agent-browser — NEVER touches the user's daily Chrome. Persistent profile + auto-login + Pythonic helpers.
---

# silent-browser-use — Skill instructions for Claude / GPT / any LLM

# 🚨 HARD RULE — DO NOT VIOLATE 🚨

**This skill operates ONLY on a dedicated Chrome instance (port 9333) that
silent-browser-use spawns and owns. It NEVER attaches the user's daily Chrome.**

- ✅ ALLOWED: `ChromeProfile(port=9333).start()` — spawn dedicated chrome
- ❌ FORBIDDEN: `set_cdp_port(9222)` — that's the user's daily Chrome (raises RuntimeError)
- ❌ FORBIDDEN: `agent-browser tab list` / `tab t2` on port 9222 — touches user's tabs
- ❌ FORBIDDEN: any "borrow user chrome to bypass cloudflare" workaround

**All silent-browser-use operations happen in a hidden window of the spawned
9333 chrome, off-screen at (-32000, -32000). The user never sees it,
silent-browser-use NEVER pops to foreground unless first-time setup explicitly
calls `show_window()`, after which `hide_window()` is mandatory.**

If 9333 chrome runs into Cloudflare, the answer is: (1) one-time visible
setup so user clicks Cloudflare + cookies persist to dedicated profile, OR
(2) integrate undetected-chromedriver to remove webdriver fingerprint. NEVER
fall back to the user's daily Chrome.

See: memory `feedback_browser_separate_instance_HARD.md`.

---

This skill wraps [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
and adds persistent Chrome profile + auto-login. The user has logged into common
sites (Nexus, GitHub, Notion, Bilibili, etc.) ONCE in the dedicated Chrome
profile — your job is to use those existing sessions, never to ask them to
log in again unless they truly haven't yet.

## When to use

- ANY URL-touching task: scrape, click, fill, screenshot, wait for SPA, etc.
- ANY task that needs the user's real cookies (Nexus mod page, private GitHub repo, internal dashboard, Bilibili, …).
- ANY task that should persist across Claude sessions (cookies, opened tabs, etc.).

## When NOT to use

- Pure HTTP API calls with no auth or where `requests` / `gh api` / `curl` is enough → use those, faster.
- Reading a public GitHub README → `gh api repos/<o>/<r>/readme`, no browser needed.
- Anything that runs in CI / headless servers → use upstream `agent-browser` directly (it's headless-friendly), this skill is for the user's local desktop.

## First-run setup for login-walled sites (one-time)

For sites behind Cloudflare or sign-in walls (Nexus Mods, Patreon, internal
dashboards), you must complete login ONCE in the dedicated Chrome profile
so cookies persist on disk:

```python
from silent_browser_use import ChromeProfile, open_url
profile = ChromeProfile()
profile.start(visible=True)   # NEW: chrome appears maximized on primary monitor
open_url("https://www.nexusmods.com/")
# user manually clicks Cloudflare + signs in
# cookies are written to ~/.silent-browser-use/chrome-profile/
# every future task uses these cookies
```

Notes on Cloudflare-protected sites:
- `navigator.webdriver` flag is set true by Chrome v8 whenever
  `--remote-debugging-port` is used. We patch plugins/languages/WebGL via
  stealth.js but **cannot delete the v8-level webdriver flag** without
  patching the chrome binary (undetected-chromedriver does this).
- This means **fresh Cloudflare challenges may still block** even with
  stealth.js. Once the user manually completes the challenge ONCE while
  signed in, Cloudflare cookies + Nexus session cookies persist and bypass
  challenges on subsequent visits.

## Quick start (3 commands)

```bash
# one-time, idempotent — installs agent-browser, starts dedicated Chrome,
# registers OS autostart so the dedicated Chrome survives reboot
sbu install

# every task afterwards — Pythonic
python -c "from silent_browser_use import open_url, get_title; \
            open_url('https://example.com'); print(get_title())"

# or natural language (delegated to agent-browser chat)
sbu run "find a Nexus mod by id 12345 and dump description"
```

## Core API (Python) — 40+ helpers, 100% coverage of agent-browser

```python
from silent_browser_use import (
    # connection
    ChromeProfile, connect, set_cdp_port, install, is_installed,
    # login UX
    LoginFlow, with_login_flow, detect_login_required,
    # core ops
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
    # semantic locators (ARIA / text / label / placeholder / etc)
    find_role, find_text, find_label, find_placeholder, find_alt,
    find_title, find_testid, find_first, find_last, find_nth,
    # waits / output
    wait, pdf, evaluate, close,
    # natural-language drive
    chat,
    # escape hatch (any agent-browser command not wrapped above)
    run,
)
```

`run("any", "command", "args...")` directly invokes `agent-browser` with
those args, so even if a future agent-browser flag isn't wrapped, you can
still use it: `run("screenshot", "--annotate", "out.png")`.

## Hard rules (NEVER violate)

1. **NEVER ask the user "please open a browser and log in" generically.**
   - The user has already logged into common sites in the dedicated profile.
   - First, just try the task. If it works, done.
   - Only invoke the login flow IF AND ONLY IF you detect a login wall (see below).

2. **NEVER spawn a fresh Chrome.**
   - Always go through `ChromeProfile()`. It is idempotent — if Chrome is already on port 9222, it returns immediately. If not, it starts the dedicated one.

3. **NEVER use `WebFetch` / `requests.get(url)` for sites that need cookies.**
   - The whole point of this skill is your real session. Bypassing it = anonymous request = different result.

4. **NEVER tell the user to "double-click a .bat" / "pin to taskbar" / "tick a checkbox in chrome://inspect".**
   - The only manual user action permitted is **typing username/password** when a login wall fires.
   - Everything else is automated by you.

5. **NEVER bypass the snapshot-first principle.**
   - Default: `snapshot()` returns the a11y tree with `@e<n>` refs → use those refs in `click_ref` / `fill_ref` (via agent-browser native commands).
   - Screenshots only as fallback for canvas / video / pure-visual targets.

6. **NEVER leave the window visible after a login flow.**
   - `LoginFlow.request_login()` automatically calls `hide_window()` after the user confirms. Do not skip this.

## Login flow — how to handle a login wall

```python
from silent_browser_use import open_url, snapshot, get_url, ChromeProfile, LoginFlow
from silent_browser_use.login_flow import detect_login_required

profile = ChromeProfile()
profile.start()  # idempotent

target = "https://www.nexusmods.com/profile"
open_url(target)

if detect_login_required(snapshot(), get_url()):
    # user has not logged into this site in the dedicated profile yet
    flow = LoginFlow(profile)
    flow.request_login("Nexus Mods")
    open_url(target)  # retry after login

# proceed with task — cookies persist forever after this one login
```

What `request_login()` does behind the scenes:

1. `profile.show_window()` — moves the dedicated Chrome from off-screen
   `(-32000, -32000)` to on-screen `(200, 100)` and z-tops it.
2. Prints to stderr: `[silent-browser-use] Please log in to Nexus Mods in
   the browser window. Press Enter when done...`
3. Reads stdin (`input()`) — blocks until user types Enter.
4. `profile.hide_window()` — pushes back to `(-32000, -32000)`.

**You as the LLM**: when this fires, in your chat to the user, say one short
sentence: "Logging into Nexus Mods is needed — the browser is open on your
desktop, please type your password and Enter to continue." Then wait for
their next message.

## Common task templates

### A) Open + read

```python
from silent_browser_use import open_url, get_title, snapshot
open_url("https://example.com")
print(get_title())
print(snapshot()[:500])
```

### B) Login-once, browse forever

```python
from silent_browser_use import open_url, snapshot, get_url, ChromeProfile, LoginFlow
from silent_browser_use.login_flow import detect_login_required

profile = ChromeProfile(); profile.start()
open_url("https://www.nexusmods.com/profile")
if detect_login_required(snapshot(), get_url()):
    LoginFlow(profile).request_login("Nexus Mods")
    open_url("https://www.nexusmods.com/profile")
# from now on, every Nexus task in this session AND every future session
# starts already logged in — nothing more to do.
```

### C) Form fill

```python
from silent_browser_use import open_url, fill, find_role
open_url("https://example.com/contact")
fill("#email", "you@example.com")
fill("textarea[name=message]", "hello")
find_role("button", "click", name="Submit")
```

### D) Multi-page scrape

```python
from silent_browser_use import open_url, get_text, snapshot
ids = [12345, 12346, 12347]
for mod_id in ids:
    open_url(f"https://www.nexusmods.com/baldursgate3/mods/{mod_id}")
    print(mod_id, "::", get_text("h1.title")[:80])
```

### E) Natural language drive

```python
from silent_browser_use import chat
result = chat("find the latest BG3 mod tagged 'patch 8' and print its description")
print(result)
```

## Failure modes & recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| `agent-browser: command not found` | npm not installed or `sbu install` not run | Run `sbu install` once. |
| `port 9222 not listening` | Dedicated Chrome got killed | `ChromeProfile().start()` — it's idempotent and self-healing. |
| `login required` re-fires every task | Cookies expired or user logged out | Re-run login flow once. |
| `click(selector)` no-op | Selector stale / page rerender | `snapshot()` again, use `@e<n>` refs from the fresh tree. |
| Pop-up "Allow remote debugging?" | Way 1 path triggered (should never happen with this skill) | `ChromeProfile().stop(); ChromeProfile().start()` to force Way 2. |

## Architecture (one-liner)

```
your code  →  silent_browser_use python helpers  →  agent-browser CLI subprocess
                          ↓                                    ↓
                 ChromeProfile (port 9222)  ←—  CDP  →  dedicated Chrome
                          ↑
                    persistent profile dir
                    (~/.silent-browser-use/chrome-profile/)
                    cookies / extensions / logged-in sessions
```

## See also

- Upstream: <https://github.com/vercel-labs/agent-browser> (the actual
  browser-automation engine — credit goes to Vercel Labs)
- Inspiration: <https://github.com/browser-use/browser-harness> (the
  persistent-agent-window pattern)
- Project repo: <https://github.com/Jcxu97/silent-browser-use>
