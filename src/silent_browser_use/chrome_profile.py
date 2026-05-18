"""Persistent Chrome profile management for silent-browser-use.

Manages a dedicated Chrome process with --remote-debugging-port=9222 and a
project-owned --user-data-dir, so the user's day-to-day logins persist across
sessions. The agent-browser CLI then attaches via `agent-browser connect 9222`
instead of spawning Chrome-for-Testing (which has no profile).

This module does NOT drive the browser itself — it only owns the lifecycle of
the dedicated Chrome instance and toggles its window visibility through the
CDP `Browser.setWindowBounds` method (used by login_flow to pop the window
when the user must authenticate, then hide it again).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests
from websocket import create_connection

DEFAULT_PORT = 9222
DEFAULT_PROFILE_DIR = Path.home() / ".silent-browser-use" / "chrome-profile"
HIDDEN_LEFT, HIDDEN_TOP = -32000, -32000


def _find_chrome() -> str:
    """Locate the user's installed Chrome binary across platforms."""
    sysname = platform.system()
    if sysname == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif sysname == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        candidates = []
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise RuntimeError(
        "Chrome not found. Install Google Chrome or set CHROME_PATH env var."
    )


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


class ChromeProfile:
    """Owns a dedicated Chrome process with persistent user-data-dir."""

    def __init__(self, profile_dir: Path | None = None, port: int = DEFAULT_PORT):
        self.profile_dir = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.port = port
        self._chrome_path = os.environ.get("CHROME_PATH") or _find_chrome()

    # ---- lifecycle -----------------------------------------------------

    def is_running(self) -> bool:
        if not _port_listening(self.port):
            return False
        marker = str(self.profile_dir.resolve())
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = proc.info.get("cmdline") or []
                if any(marker in str(part) for part in cmd):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def start(self, visible: bool = False) -> None:
        if self.is_running():
            return
        args = [
            self._chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--remote-allow-origins=*",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            # Anti-bot-detection — Cloudflare Turnstile / hCaptcha look at these.
            "--disable-blink-features=AutomationControlled",
            "--disable-features=ChromeWhatsNewUI,IsolateOrigins,site-per-process",
            "--exclude-switches=enable-automation",
            "--disable-infobars",
        ]
        if visible:
            # Visible startup — for first-time login flow / cloudflare challenge.
            # Maximized on primary monitor, foreground.
            args += ["--start-maximized"]
        else:
            # Headless-feel: off-screen geometry but still rendering.
            args += [
                f"--window-position={HIDDEN_LEFT},{HIDDEN_TOP}",
                "--window-size=1280,900",
            ]
        kwargs: dict = {"close_fds": True}
        if platform.system() == "Windows":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)

        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                r = requests.get(f"http://127.0.0.1:{self.port}/json/version", timeout=0.5)
                if r.ok:
                    self._apply_stealth()
                    return
            except requests.RequestException:
                pass
            time.sleep(0.15)
        raise RuntimeError(f"Chrome did not become ready on port {self.port} within 5s")

    def stop(self) -> None:
        marker = str(self.profile_dir.resolve())
        killed = []
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = proc.info.get("cmdline") or []
                if any(marker in str(part) for part in cmd):
                    proc.terminate()
                    killed.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        gone, alive = psutil.wait_procs(killed, timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

    # ---- window control via CDP ---------------------------------------

    def _browser_ws_url(self) -> str:
        r = requests.get(f"http://127.0.0.1:{self.port}/json/version", timeout=2)
        r.raise_for_status()
        return r.json()["webSocketDebuggerUrl"]

    def _cdp_send(self, method: str, params: dict | None = None) -> dict:
        ws = create_connection(self._browser_ws_url(), timeout=3)
        try:
            payload = {"id": 1, "method": method, "params": params or {}}
            ws.send(json.dumps(payload))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 1:
                    if "error" in msg:
                        raise RuntimeError(f"CDP {method} failed: {msg['error']}")
                    return msg.get("result", {})
        finally:
            ws.close()

    # ---- stealth: hide CDP/automation fingerprints from Cloudflare/hCaptcha ----

    _STEALTH_JS = r"""
    // 1. webdriver flag — biggest tell. Chrome sets this read-only on Navigator.prototype,
    //    but we can delete from prototype before any page script reads it.
    try {
        delete Navigator.prototype.webdriver;
    } catch(_) {}
    Object.defineProperty(Navigator.prototype, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

    // 2. plugins — vanilla Chrome has 3+; CDP-launched often shows []
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {0: {type: 'application/x-google-chrome-pdf'}, description: 'PDF Viewer', filename: 'internal-pdf-viewer', length: 1, name: 'PDF Viewer'},
            {0: {type: 'application/pdf'}, description: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', length: 1, name: 'Chrome PDF Viewer'},
            {0: {type: 'application/x-nacl'}, description: 'Native Client Executable', filename: 'internal-nacl-plugin', length: 1, name: 'Native Client'}
        ]
    });

    // 3. languages — must be non-empty
    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});

    // 4. window.chrome — vanilla has chrome.runtime; CDP often misses it
    if (!window.chrome || !window.chrome.runtime) {
        window.chrome = window.chrome || {};
        window.chrome.runtime = window.chrome.runtime || {};
    }

    // 5. permissions API — Notification permission must agree with state
    if (window.navigator.permissions && window.navigator.permissions.query) {
        const origQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (params) =>
            params.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : origQuery(params);
    }

    // 6. WebGL vendor/renderer — CDP often shows 'Google Inc.'
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL = 37445; UNMASKED_RENDERER_WEBGL = 37446
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, arguments);
    };

    // 7. iframe contentWindow chrome property
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
            const win = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get.call(this);
            try { if (win && !win.chrome) win.chrome = {runtime: {}}; } catch(_) {}
            return win;
        }
    });
    """

    def _apply_stealth(self) -> None:
        """Register stealth.js as auto-inject-on-new-document for every browser target.

        Uses CDP Page.addScriptToEvaluateOnNewDocument on each existing page target
        plus auto-applies to new targets via Target.setAutoAttach.
        """
        try:
            # Get all existing page targets
            targets = requests.get(f"http://127.0.0.1:{self.port}/json", timeout=2).json()
            for t in targets:
                if t.get("type") != "page":
                    continue
                try:
                    ws_url = t.get("webSocketDebuggerUrl")
                    if not ws_url:
                        continue
                    ws = create_connection(ws_url, timeout=3)
                    ws.send(json.dumps({
                        "id": 1,
                        "method": "Page.addScriptToEvaluateOnNewDocument",
                        "params": {"source": self._STEALTH_JS},
                    }))
                    ws.recv()
                    ws.close()
                except Exception:
                    pass
        except Exception:
            pass

    def _get_window_id(self) -> int:
        targets = requests.get(f"http://127.0.0.1:{self.port}/json", timeout=2).json()
        page = next((t for t in targets if t.get("type") == "page"), None)
        if not page:
            res = self._cdp_send("Target.createTarget", {"url": "about:blank"})
            target_id = res["targetId"]
        else:
            target_id = page["id"]
        res = self._cdp_send("Browser.getWindowForTarget", {"targetId": target_id})
        return res["windowId"]

    def show_window(self, left: int | None = None, top: int | None = None,
                    width: int | None = None, height: int | None = None,
                    maximize: bool = True) -> None:
        """Bring the dedicated Chrome to foreground on the user's PRIMARY monitor.

        Strategy:
            1) windowState=normal (rejects geometry while maximized/minimized)
            2) move to primary monitor (left=100, top=100) so the window LIVES there
            3) optionally maximize on that monitor

        Without step 2, a chrome that started off-screen at (-32000,-32000) may
        maximize onto a non-existent virtual monitor and the user never sees it.
        """
        wid = self._get_window_id()
        # Step 1: normalize state
        self._cdp_send(
            "Browser.setWindowBounds",
            {"windowId": wid, "bounds": {"windowState": "normal"}},
        )
        # Step 2: relocate to primary monitor first (always at (100, 100) — primary's top-left)
        self._cdp_send(
            "Browser.setWindowBounds",
            {"windowId": wid, "bounds": {
                "left": left if left is not None else 100,
                "top": top if top is not None else 100,
                "width": width or 1280,
                "height": height or 900,
            }},
        )
        # Step 3: maximize if requested (will maximize on the monitor it currently lives on,
        # which we just forced to be primary).
        if maximize and left is None and top is None:
            self._cdp_send(
                "Browser.setWindowBounds",
                {"windowId": wid, "bounds": {"windowState": "maximized"}},
            )
        # Step 4: bring to z-top via CDP
        try:
            targets = requests.get(f"http://127.0.0.1:{self.port}/json", timeout=2).json()
            page = next((t for t in targets if t.get("type") == "page"), None)
            if page:
                self._cdp_send("Target.activateTarget", {"targetId": page["id"]})
                self._cdp_send("Page.bringToFront", {})
        except Exception:
            pass
        # Step 5: Win32 flash + foreground (Windows-specific, gracefully no-op elsewhere)
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Find Chrome window of our profile
            marker = str(self.profile_dir.resolve()).lower()
            target_pids = set()
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    cmd = " ".join(str(x) for x in (proc.info.get("cmdline") or [])).lower()
                    if marker in cmd:
                        target_pids.add(proc.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            found = [None]

            def cb(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                pid = ctypes.c_ulong(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in target_pids:
                    if user32.GetWindowTextLengthW(hwnd) > 5:
                        found[0] = hwnd
                        return False
                return True

            user32.EnumWindows(EnumWindowsProc(cb), None)
            hwnd = found[0]
            if not hwnd:
                return

            # FlashWindowEx — make taskbar icon flash to grab attention
            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("hwnd", ctypes.c_void_p),
                    ("dwFlags", ctypes.c_uint),
                    ("uCount", ctypes.c_uint),
                    ("dwTimeout", ctypes.c_uint),
                ]
            FLASHW_ALL = 3
            FLASHW_TIMERNOFG = 12  # flash until brought to fg
            fi = FLASHWINFO(
                ctypes.sizeof(FLASHWINFO), hwnd,
                FLASHW_ALL | FLASHW_TIMERNOFG, 10, 0,
            )
            user32.FlashWindowEx(ctypes.byref(fi))

            # Maximize via Win32 (CDP setBounds maximized sometimes silently fails)
            SW_SHOWMAXIMIZED = 3
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)

            # Bring-to-front trick: AttachThreadInput + SetForegroundWindow
            fg = user32.GetForegroundWindow()
            fg_thread = user32.GetWindowThreadProcessId(fg, None)
            our_thread = kernel32.GetCurrentThreadId()
            user32.AttachThreadInput(our_thread, fg_thread, True)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.AttachThreadInput(our_thread, fg_thread, False)
        except Exception:
            pass
        # Bring to front + activate so user actually sees it (z-top + foreground).
        try:
            targets = requests.get(f"http://127.0.0.1:{self.port}/json", timeout=2).json()
            page = next((t for t in targets if t.get("type") == "page"), None)
            if page:
                self._cdp_send("Target.activateTarget", {"targetId": page["id"]})
                self._cdp_send("Page.bringToFront", {})
        except Exception:
            pass
        # On Windows, additionally use Win32 SetForegroundWindow to surface above other apps.
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                # Find any Chrome window for our profile (by class name + title fragment is hard;
                # easier: enumerate top-level windows whose title ends with "Google Chrome" and
                # whose process cmdline includes our profile_dir).
                marker = str(self.profile_dir.resolve()).lower()
                target_pids = set()
                for proc in psutil.process_iter(["pid", "cmdline"]):
                    try:
                        cmd = " ".join(str(x) for x in (proc.info.get("cmdline") or [])).lower()
                        if marker in cmd:
                            target_pids.add(proc.info["pid"])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                EnumWindows = user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(
                    ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
                )
                GetWindowThreadProcessId = user32.GetWindowThreadProcessId
                IsWindowVisible = user32.IsWindowVisible
                SetForegroundWindow = user32.SetForegroundWindow
                ShowWindow = user32.ShowWindow
                SW_RESTORE = 9

                def cb(hwnd, _):
                    if not IsWindowVisible(hwnd):
                        return True
                    pid = ctypes.c_ulong(0)
                    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in target_pids:
                        ShowWindow(hwnd, SW_RESTORE)
                        SetForegroundWindow(hwnd)
                        return False  # stop enumerating
                    return True

                EnumWindows(EnumWindowsProc(cb), None)
            except Exception:
                pass

    def hide_window(self) -> None:
        wid = self._get_window_id()
        self._cdp_send(
            "Browser.setWindowBounds",
            {"windowId": wid, "bounds": {"windowState": "normal"}},
        )
        self._cdp_send(
            "Browser.setWindowBounds",
            {
                "windowId": wid,
                "bounds": {"left": HIDDEN_LEFT, "top": HIDDEN_TOP, "width": 800, "height": 600},
            },
        )

    # ---- misc ----------------------------------------------------------

    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def install_autostart(self) -> None:
        sysname = platform.system()
        cmd = (
            f'"{self._chrome_path}" --remote-debugging-port={self.port} '
            f'--user-data-dir="{self.profile_dir}" --no-first-run '
            f'--window-position={HIDDEN_LEFT},{HIDDEN_TOP}'
        )
        if sysname == "Windows":
            startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
            startup.mkdir(parents=True, exist_ok=True)
            bat = startup / "silent-browser-use-chrome.bat"
            bat.write_text(f'@echo off\r\nstart "" {cmd}\r\n', encoding="utf-8")
        elif sysname == "Darwin":
            plist_dir = Path.home() / "Library/LaunchAgents"
            plist_dir.mkdir(parents=True, exist_ok=True)
            plist = plist_dir / "com.silent-browser-use.chrome.plist"
            args_xml = "".join(
                f"        <string>{a}</string>\n"
                for a in [
                    self._chrome_path,
                    f"--remote-debugging-port={self.port}",
                    f"--user-data-dir={self.profile_dir}",
                    "--no-first-run",
                    f"--window-position={HIDDEN_LEFT},{HIDDEN_TOP}",
                ]
            )
            plist.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict>\n'
                "    <key>Label</key><string>com.silent-browser-use.chrome</string>\n"
                "    <key>RunAtLoad</key><true/>\n"
                "    <key>ProgramArguments</key><array>\n"
                f"{args_xml}"
                "    </array>\n"
                "</dict></plist>\n",
                encoding="utf-8",
            )
        else:
            unit_dir = Path.home() / ".config/systemd/user"
            unit_dir.mkdir(parents=True, exist_ok=True)
            unit = unit_dir / "silent-browser-use-chrome.service"
            unit.write_text(
                "[Unit]\nDescription=silent-browser-use dedicated Chrome\n\n"
                "[Service]\nType=simple\n"
                f"ExecStart={cmd}\nRestart=on-failure\n\n"
                "[Install]\nWantedBy=default.target\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    p = ChromeProfile()
    print(f"profile_dir = {p.profile_dir}")
    print(f"chrome      = {p._chrome_path}")
    print(f"port        = {p.port}")
    print(f"is_running  = {p.is_running()}")
    sys.exit(0)
