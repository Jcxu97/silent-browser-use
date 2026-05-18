"""Quickstart: open a page and dump its title — five lines, no config.

Prerequisites:
    pip install silent-browser-use
    sbu install            # one-time: installs agent-browser + persistent Chrome
"""

from silent_browser_use import open_url
from silent_browser_use.helpers import get_title

open_url("https://example.com")
print("Title:", get_title())
