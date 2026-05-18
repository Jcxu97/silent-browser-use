<div align="center">

<!-- TODO: drop a real logo here. Until then this ASCII placeholder ships. -->

```
  ┌─────────────────────────────────────────┐
  │   silent-browser-use                    │
  │   ─ your real Chrome, agent-driven ─    │
  └─────────────────────────────────────────┘
```

# silent-browser-use

**Use [agent-browser](https://github.com/vercel-labs/agent-browser) with your *real* logged-in Chrome.**
A tiny Python companion toolkit — persistent profile, auto-login flow, Pythonic helpers.

[![PyPI version](https://img.shields.io/pypi/v/silent-browser-use.svg)](https://pypi.org/project/silent-browser-use/)
[![Python](https://img.shields.io/pypi/pyversions/silent-browser-use.svg)](https://pypi.org/project/silent-browser-use/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![agent-browser](https://img.shields.io/badge/built_on-agent--browser-black.svg)](https://github.com/vercel-labs/agent-browser)
[![GitHub stars](https://img.shields.io/github/stars/Jcxu97/silent-browser-use?style=social)](https://github.com/Jcxu97/silent-browser-use/stargazers)

[English](README.md) · [中文](README_zh.md)

</div>

---

## What is this?

> **TL;DR — agent-browser is amazing, but it ships a clean Chrome-for-Testing binary with no logins.
> silent-browser-use gives it your real Chrome profile, with a one-shot login flow.**

[agent-browser](https://github.com/vercel-labs/agent-browser) is a brilliant Rust CLI from Vercel Labs that lets LLM agents drive a browser. Out of the box it launches a fresh, isolated Chrome-for-Testing instance — perfect for CI, painful for "open my Notion, log into Nexus, click around my GitHub".

**silent-browser-use** is a small Python toolkit that sits *next to* agent-browser and adds:

- **A dedicated Chrome window**, started once, kept alive on `--remote-debugging-port=9222`, with its own persistent profile dir. Every login you do — Google, GitHub, Nexus Mods, Bilibili, Notion, Linear, your bank — stays logged in **forever**.
- **Auto-login choreography**. When the agent hits a login wall, silent-browser-use focuses the window, waits for *you* to type the password, and steps out the moment you're in. No mouse, no rage.
- **A Pythonic API** (`open_url`, `click`, `fill`, `snapshot`) that wraps the agent-browser CLI as a subprocess. Your agent-browser version updates? We pick it up automatically — no fork to maintain.
- **Vertical recipes** for the workflows we actually run: BG3 Nexus mod scraping, BG3 mod-translation pipelines, Bilibili / Zhihu / Xiaohongshu data, multi-page e-commerce flows.

We do **not** fork agent-browser. We do **not** compete with it. We make it pleasant to use with your real life on top of it.

---

## 30-second demo

<!-- TODO: record asciinema/GIF and replace -->

```text
[GIF placeholder] sbu install → sbu login nexusmods.com →
                  python -c "from silent_browser_use import open_url; open_url('https://nexusmods.com')"
                  → already logged in, agent does its thing
```

```python
from silent_browser_use import open_url, click, fill, snapshot

# Reuses your dedicated Chrome on port 9222.
# If you've ever logged into Nexus from this profile, you still are.
open_url("https://www.nexusmods.com/baldursgate3/mods/12345")

shot = snapshot()                     # ARIA tree + screenshot
click(role="link", name="Files")
print(snapshot().text)                # dump page text for the agent
```

That's the entire mental model. Everything else is plumbing we hide.

---

## Why silent-browser-use?

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            your code / agent                             │
│        (Python, Claude, GPT-4o, your custom orchestrator, …)             │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  silent-browser-use  (this repo, Python)                 │
│                                                                          │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│   │ Pythonic helpers │  │ Profile manager  │  │ Auto-login flow      │   │
│   │ open_url/click/… │  │ port 9222 daemon │  │ focus → wait → hide  │   │
│   └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘   │
└────────────┼─────────────────────┼─────────────────────────┼─────────────┘
             │                     │                         │
             ▼ subprocess          ▼ launches/attaches       ▼ OS signals
┌──────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│ agent-browser (Rust) │    │  dedicated Chrome    │    │ user keyboard   │
│  vercel-labs CLI     │◀──▶│  --user-data-dir     │◀──▶│ password input  │
│  (CDP client)        │ CDP│  --remote-debugging  │    │ (no mouse req.) │
└──────────────────────┘    └──────────────────────┘    └─────────────────┘
```

Three things to notice:

1. **agent-browser does all the heavy lifting** — DOM serialisation, ARIA snapshots, click/fill, screenshots. We don't reimplement any of it.
2. **Chrome is yours.** It's a separate Chrome instance on its own profile dir. It has cookies, IndexedDB, extensions. It survives reboots.
3. **The auto-login flow** is the single trick: when a script encounters a login page, we surface the window, you type, we hide it. Cookies persist, your next 1,000 runs see you logged in.

---

## Installation

```bash
pip install silent-browser-use
sbu install        # downloads agent-browser, sets up dedicated Chrome profile
```

`sbu install` is idempotent. It:

1. Installs the `agent-browser` binary (per the upstream installer) if missing.
2. Locates your system Chrome (or downloads Chrome-for-Testing as a fallback).
3. Creates a profile dir at `~/.silent-browser-use/chrome-profile/`.
4. Starts Chrome on port `9222` and writes a tiny PID file so we don't double-launch.

Tested on **Windows 10/11, macOS 13+, Ubuntu 22.04+**. Python 3.10+.

---

## Quick start

### 1. Open a URL with your real cookies

```python
from silent_browser_use import open_url

open_url("https://github.com")    # already logged in if you ever logged in
```

### 2. Log into a site once, forever

```bash
sbu login nexusmods.com
# Window pops up. Enter password / 2FA. Window closes.
# All future runs see you as logged in.
```

### 3. Drive a page

```python
from silent_browser_use import open_url, click, fill, snapshot

open_url("https://github.com/login")
fill(role="textbox", name="Username", value="octocat")
fill(role="textbox", name="Password", value="…")
click(role="button", name="Sign in")
print(snapshot().text)
```

### 4. Run an agent prompt

```bash
sbu run "find the top mod for Baldur's Gate 3 on Nexus and print its description"
```

Under the hood: we hand the prompt to agent-browser, which connects to your dedicated Chrome via CDP. You stay logged in. The agent works.

---

## Features

- **Persistent profile** — every cookie, localStorage entry, and extension survives between runs and reboots.
- **One-shot logins** — `sbu login <domain>` opens a focused window, waits for you, then hides. No script babysits a flaky 2FA flow.
- **Pythonic helpers** — `open_url`, `click`, `fill`, `snapshot`, `wait_for`, `screenshot`, `goto`, `eval_js`. See [examples/](examples/).
- **CLI parity** — `sbu run "<prompt>"` mirrors `agent-browser run` but defaults to your profile.
- **Single window, single port** — by design, we never spawn random tabs in random windows. Multi-tab orchestration is opt-in.
- **Snapshot-first ergonomics** — `snapshot()` returns the ARIA tree, refs, and a screenshot in one call. Inspired by browser-use's snapshot-first style.
- **Vertical recipes** — `examples/bg3_nexus_scrape.py`, `examples/bg3_mod_translate.py`, `examples/bilibili_subtitles.py`, `examples/zhihu_question.py` ship as starter code.

---

## silent-browser-use vs alternatives

| Capability                                     | agent-browser alone | playwright | silent-browser-use |
| ---------------------------------------------- | :-----------------: | :--------: | :----------------: |
| Drive Chrome from an LLM agent prompt          |          ✅         |     —      |   ✅ *(via agent-browser)* |
| Persistent profile with your real logins       |          —          |     ⚠️[^1] |          ✅        |
| Auto-launch / re-attach to one Chrome instance |          —          |     —      |          ✅        |
| Auto-login flow (window pop / hide on success) |          —          |     —      |          ✅        |
| Pythonic helper API                            |          —          |     ✅     |          ✅        |
| ARIA snapshot + screenshot in one call         |          ✅         |     ⚠️     |          ✅        |
| Stealth / undetectable patches                 |          —          |     ⚠️     |          —[^2]     |
| Multi-browser (Firefox / WebKit)               |          —          |     ✅     |          —         |
| Best for CI / clean-room automation            |          ✅         |     ✅     |          —         |
| Best for "use my real account" automation      |          —          |     —      |          ✅        |

[^1]: Playwright supports persistent context but you wire profile management, port pinning, and login UX yourself.
[^2]: Use [rebrowser-patches](https://github.com/rebrowser/rebrowser-patches) or upstream tools if you need stealth. Our scope is *your* browser, not anonymous scraping.

> **Use agent-browser directly** when you want clean-room automation, CI, or zero login state. Use silent-browser-use when you want your real life in the loop.

---

## Common recipes

All recipes assume `sbu install` has been run.

### Recipe 1 — Open, click, fill (the canonical first task)

```python
from silent_browser_use import open_url, fill, click, snapshot

open_url("https://duckduckgo.com")
fill(role="textbox", name="Search", value="agent-browser vercel labs")
click(role="button", name="Search")
print(snapshot().text[:500])
```

### Recipe 2 — Log in once, run forever

```bash
sbu login linear.app
# Window appears, you sign in via Google / SSO, window hides.
```

```python
from silent_browser_use import open_url, snapshot

open_url("https://linear.app/inbox")
print(snapshot().text)         # already authenticated, no prompts
```

Cookies live in `~/.silent-browser-use/chrome-profile/`. Wipe that dir to log out of everything.

### Recipe 3 — Scrape a Nexus Mods page (BG3 example)

```python
from silent_browser_use import open_url, snapshot, click

def fetch_mod(mod_id: int) -> dict:
    open_url(f"https://www.nexusmods.com/baldursgate3/mods/{mod_id}")
    s = snapshot()
    title = s.find(role="heading", level=1).text
    desc  = s.find(role="region", name="Description").text
    click(role="link", name="Files")
    s2 = snapshot()
    files = [el.text for el in s2.all(role="listitem")]
    return {"id": mod_id, "title": title, "desc": desc, "files": files}

print(fetch_mod(12345))
```

You're logged in (because you ran `sbu login nexusmods.com` once), so premium download links and adult-content flags Just Work.

### Recipe 4 — Multi-page scraping with checkpointing

```python
from silent_browser_use import open_url, snapshot, click, wait_for
import json, pathlib

out = pathlib.Path("results.jsonl").open("a", encoding="utf-8")

open_url("https://www.nexusmods.com/baldursgate3/mods/?BH=0")
while True:
    for card in snapshot().all(role="article"):
        out.write(json.dumps({"title": card.text}, ensure_ascii=False) + "\n")
    nxt = snapshot().find(role="link", name="Next")
    if not nxt:
        break
    click(ref=nxt.ref)
    wait_for(role="article")     # SPA navigation
```

### Recipe 5 — SPA wait + screenshot

```python
from silent_browser_use import open_url, wait_for, screenshot

open_url("https://app.notion.so/")
wait_for(role="heading", name_contains="Quick Find", timeout=15)
screenshot("notion-loaded.png")
```

---

## CLI reference

```text
sbu install                 # one-shot setup: agent-browser + dedicated Chrome profile
sbu start                   # ensure dedicated Chrome is running on port 9222
sbu stop                    # quit the dedicated Chrome (profile is preserved)
sbu status                  # show port, PID, profile dir, agent-browser version
sbu login <domain>          # focus window for manual login, hide on success
sbu run "<prompt>"          # forward prompt to agent-browser, attached to your profile
sbu open <url>              # quick `open_url` from the shell
sbu doctor                  # check chrome, port, agent-browser binary, profile health
```

`sbu --help` shows the full surface.

---

## Architecture deep dive

```
┌────────────────────────────────────────────────────────────────────────┐
│  Your script  ──►  silent_browser_use.open_url("…")                    │
│                            │                                           │
│                            ▼                                           │
│                    ProfileManager.ensure_running()                     │
│                            │                                           │
│                            ▼                                           │
│        ┌──────────────────────────────────────────┐                    │
│        │  Chrome (your binary, your profile dir,  │                    │
│        │  --remote-debugging-port=9222)           │                    │
│        └────────────┬─────────────────────────────┘                    │
│                     │ CDP                                              │
│                     ▼                                                  │
│        ┌──────────────────────────────────────────┐                    │
│        │  agent-browser CLI  (subprocess)         │                    │
│        │  invoked with --connect=ws://…:9222      │                    │
│        └──────────────────────────────────────────┘                    │
└────────────────────────────────────────────────────────────────────────┘
```

Design decisions worth flagging:

- **One Chrome, one port.** All Python helpers go through one `BrowserSession` singleton that points at port 9222. No accidental fan-out into orphan tabs.
- **Subprocess, not FFI.** We `subprocess.Popen(["agent-browser", "connect", "--ws", "ws://…"])` and stream JSON back. When agent-browser ships a new release, you upgrade the binary and we pick it up.
- **Profile lives in `~/.silent-browser-use/chrome-profile/`.** Backed up like any other Chrome profile. Wipe = full logout.
- **Locks via PID file.** `~/.silent-browser-use/chrome.pid` prevents racing instances. `sbu start` is idempotent.
- **No background timers.** Chrome stays alive across runs but we never poke it on a schedule. If you want shutdown, `sbu stop`.

---

## FAQ

**Q: How is this different from agent-browser?**
A: agent-browser *is* the engine. silent-browser-use is a thin wrapper that (a) keeps a persistent Chrome with your logins running, (b) gives you a Python API, (c) ships the auto-login flow. We never replace or fork agent-browser — we shell out to it.

**Q: Will I get banned from Nexus / Bilibili / etc. for scraping?**
A: This tool has nothing to do with stealth. It uses your real Chrome with your real cookies, exactly like a power user with a userscript. Be a good citizen: respect robots.txt, throttle, and don't abuse the rate limits. If a site forbids automated access in its ToS, don't use this for it.

**Q: Headless?**
A: Not by default — the entire point is your real, visible browser. You *can* pass `--headless` to the underlying Chrome via `sbu start --headless`, but then the auto-login flow is meaningless. If you want headless CI, just use agent-browser directly.

**Q: Does it work on macOS / Linux / Windows?**
A: Yes. macOS 13+, Ubuntu 22.04+, Windows 10/11. WSL2 works but cookies live in WSL — don't expect Windows Chrome to share them.

**Q: Will my Chrome profile sync to Google?**
A: Only if you sign Chrome into your Google account inside the dedicated profile. By default it's a fresh, unsynced profile separate from your daily Chrome.

**Q: Can I use my regular Chrome profile?**
A: Strongly discouraged. CDP access (port 9222) requires Chrome to start with specific flags; mixing with your daily browser is a recipe for crashes and lost tabs. The dedicated profile is cheap (a few MB) and isolated.

**Q: Does this support Firefox / WebKit?**
A: No. agent-browser is Chrome-only via CDP, and so are we.

**Q: What about CAPTCHAs?**
A: When the agent hits a CAPTCHA, the auto-login flow surfaces the window, you solve it, the agent continues. Same primitive as login.

**Q: Is the API stable?**
A: We're at `0.1.x` — breaking changes are possible until `1.0`. Pin a version. The CLI surface (`sbu install`, `sbu login`, `sbu run`) is what we intend to keep stable first.

---

## Roadmap

- [ ] `sbu install` cross-platform installer for agent-browser
- [ ] `sbu doctor` health checks
- [ ] First-class auto-login UX (window focus / hide on macOS / Linux)
- [ ] Recipes: BG3 Nexus, BG3 mod translation, Bilibili subtitles, Zhihu, Xiaohongshu
- [ ] Pluggable session storage (multiple profiles)
- [ ] Async API (`from silent_browser_use.aio import open_url`)
- [ ] `sbu record` → emit a Python script from manual clicks

PRs welcome. See [CONTRIBUTING](#contributing).

---

## Contributing

We especially welcome:

- **Vertical recipes** in `examples/`. If you scraped a site cleanly, ship the script.
- **Chinese-community vertical case studies** — Bilibili, Zhihu, Xiaohongshu, JD, Nexus 中文站. We ship a Chinese README and we mean it.
- **Auto-login polish** for macOS and Linux window-focus quirks.
- **Docs**. Especially anything that would have saved you an hour.

```bash
git clone https://github.com/Jcxu97/silent-browser-use
cd silent-browser-use
pip install -e ".[dev]"
pytest
```

Be kind to upstream. If a bug is in agent-browser, file it [there](https://github.com/vercel-labs/agent-browser/issues).

---

## Credits & acknowledgements

silent-browser-use stands on the shoulders of:

- **[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)** — the actual browser-automation engine. Apache 2.0. Without it this project is an empty shell. We do not fork it — we subprocess it.
- **[browser-use/browser-harness](https://github.com/browser-use/browser-use)** — the *persistent agent window* design pattern (one window, many sessions, snapshot-first ergonomics) inspired the whole UX of this toolkit. MIT.
- **[Playwright](https://playwright.dev)** & **[Puppeteer](https://pptr.dev)** — the granddaddies; many of our helper signatures rhyme with theirs.
- The **Chinese mod / agent dev community** that pushed for "let me use my real Chrome" instead of "spin up a sterile binary every time" — this whole repo is your feature request, made real.

See [NOTICE](NOTICE) for the full citation block.

---

## License

[MIT](LICENSE) © AKAK and contributors.

`agent-browser` is licensed under Apache 2.0 by Vercel Labs and contributors. We invoke its CLI as a subprocess and do not redistribute its source.

---

<div align="center">

**Built for everyone whose agent has been stuck on a login page.**
Star the repo if it saved you an hour. ★

[Report an issue](https://github.com/Jcxu97/silent-browser-use/issues) ·
[agent-browser](https://github.com/vercel-labs/agent-browser) ·
[Chinese README](README_zh.md)

</div>
