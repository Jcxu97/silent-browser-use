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

    def start(self) -> None:
        if self.is_running():
            return
        args = [
            self._chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=ChromeWhatsNewUI",
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

    def show_window(self, left: int = 200, top: int = 100, width: int = 1280, height: int = 900) -> None:
        wid = self._get_window_id()
        # First normalize state, then set bounds (CDP rejects bounds while minimized).
        self._cdp_send(
            "Browser.setWindowBounds",
            {"windowId": wid, "bounds": {"windowState": "normal"}},
        )
        self._cdp_send(
            "Browser.setWindowBounds",
            {
                "windowId": wid,
                "bounds": {"left": left, "top": top, "width": width, "height": height},
            },
        )

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
