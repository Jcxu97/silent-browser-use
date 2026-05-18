"""Log in to a site ONCE, browse it forever after.

Demonstrates the silent-browser-use core promise: a persistent Chrome profile
plus the auto-login flow means you sign in to a site exactly once, and every
future agent task runs with your real cookies — no API keys, no headless
session, no captcha-rejection loop.

Prerequisites:
    pip install silent-browser-use
    sbu install            # one-time

Run this script the first time and you'll be prompted to log in. Run it again
tomorrow / next month — no prompt, cookies still valid.
"""

from silent_browser_use import ChromeProfile, LoginFlow, open_url, snapshot
from silent_browser_use.helpers import get_url
from silent_browser_use.login_flow import detect_login_required


def main() -> None:
    profile = ChromeProfile()
    profile.start()  # idempotent — reuses if already running

    # Pick any logged-in-only page; substitute your own.
    target_url = "https://www.nexusmods.com/users/myaccount"
    open_url(target_url)

    snap = snapshot()
    url = get_url()

    if detect_login_required(snap, url):
        print("[login_once] Page looks like a login wall; popping browser ...")
        flow = LoginFlow(profile)
        ok = flow.request_login("Nexus Mods")
        if not ok:
            print("[login_once] User cancelled login. Bye.")
            return
        # Retry the original URL now that we're authenticated.
        open_url(target_url)
    else:
        print("[login_once] Already authenticated — cookies survived from a prior session.")

    print()
    print("Final URL :", get_url())
    print("First 500 chars of accessibility tree:")
    print("-" * 60)
    print(snapshot()[:500])
    print("-" * 60)
    print()
    print("Re-run this script anytime — no login prompt unless cookies expire.")


if __name__ == "__main__":
    main()
