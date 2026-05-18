"""Scrape a BG3 Nexus mod page using your logged-in Chrome.

Real-world scenario: BG3 modders / translators want to fetch mod metadata
(title, version, description, downloads, screenshots) for batch processing.
Nexus imposes both rate limits and a login wall on its public API; using a
real, logged-in Chrome via silent-browser-use sidesteps both.

This example only demonstrates the silent-browser-use API surface — parsing
the accessibility-tree snapshot into structured fields is left to the caller
(your business logic, not ours).

Prerequisites:
    pip install silent-browser-use
    sbu install                 # one-time
    sbu login nexusmods.com     # one-time: pop window, sign in, done forever

Usage:
    python bg3_nexus_scraper.py 12345              # mod ID
    python bg3_nexus_scraper.py 12345 --shot       # also save a screenshot
"""

from __future__ import annotations

import argparse
import json
import sys

from silent_browser_use import ChromeProfile, open_url, screenshot, snapshot
from silent_browser_use.helpers import get_title, get_url


def scrape_mod(mod_id: int, save_shot: bool = False) -> dict:
    """Visit a Nexus BG3 mod page and return a metadata dict."""
    url = f"https://www.nexusmods.com/baldursgate3/mods/{mod_id}"
    open_url(url)

    snap = snapshot()
    title = get_title()
    final_url = get_url()

    data: dict = {
        "id": mod_id,
        "requested_url": url,
        "final_url": final_url,
        "title": title,
        # The accessibility tree is the canonical extraction surface for
        # silent-browser-use. Downstream code should walk `snap` and call
        # `helpers.get_text("@e<ref>")` for each interesting node.
        "snapshot_excerpt": snap[:1000],
        "snapshot_chars": len(snap),
    }

    if save_shot:
        path = f"bg3_mod_{mod_id}.png"
        screenshot(path, full=True)
        data["screenshot"] = path

    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("mod_id", type=int, help="Numeric Nexus mod ID")
    ap.add_argument("--shot", action="store_true", help="Save a full-page screenshot")
    args = ap.parse_args()

    # Make sure our dedicated Chrome (with cookies) is up. agent-browser will
    # attach to it automatically because `sbu install` already ran `connect`.
    profile = ChromeProfile()
    if not profile.is_running():
        print("[bg3_nexus_scraper] Starting dedicated Chrome ...", file=sys.stderr)
        profile.start()

    data = scrape_mod(args.mod_id, save_shot=args.shot)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
