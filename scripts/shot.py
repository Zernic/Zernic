#!/usr/bin/env python3
"""Dev helper: screenshot a card so I can look at it before pushing.

    python3 scripts/shot.py assets/neofetch-dark.svg /tmp/dark.png "#0d1117"

Needs playwright. The browser is the thing that actually renders these on
GitHub, so this is the only honest preview.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

src = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()
bg = sys.argv[3] if len(sys.argv) > 3 else "#0d1117"

tmp = out.with_suffix(".html")
tmp.write_text(
    f'<html><body style="margin:0;padding:28px;background:{bg};'
    f'display:inline-block"><img src="file://{src}" width="900"></body></html>'
)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 960, "height": 560}, device_scale_factor=2)
    page.goto(f"file://{tmp}")
    page.wait_for_timeout(600)
    page.locator("body").screenshot(path=str(out))
    browser.close()
tmp.unlink()
print(out)
