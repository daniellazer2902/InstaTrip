from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from rich.console import Console

console = Console()

POST_HREF_RE = re.compile(r"^/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?")


def parse_post_links(html: str) -> list[str]:
    """Parse la HTML d'une page collection et retourne la liste
    ordonnée et dédupliquée des shortcodes."""
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        m = POST_HREF_RE.match(a["href"])
        if m:
            seen.setdefault(m.group(1), None)
    return list(seen.keys())


def collect_shortcodes(collection_url: str, state_path: Path, max_scrolls: int = 200) -> list[str]:
    """Ouvre la collection Instagram et scrolle jusqu'à ce qu'aucun
    nouveau shortcode n'apparaisse pendant 5 itérations."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        page.goto(collection_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        shortcodes: list[str] = []
        stable_iters = 0
        for i in range(max_scrolls):
            html = page.content()
            new_codes = parse_post_links(html)
            before = len(shortcodes)
            for c in new_codes:
                if c not in shortcodes:
                    shortcodes.append(c)
            grew = len(shortcodes) > before
            console.print(f"[cyan]scroll {i+1}: {len(shortcodes)} shortcodes")
            if not grew:
                stable_iters += 1
                if stable_iters >= 5:
                    break
            else:
                stable_iters = 0
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1500)
        browser.close()
        return shortcodes
