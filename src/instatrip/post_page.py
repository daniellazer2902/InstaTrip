from __future__ import annotations

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def parse_post_html(html: str) -> dict:
    """Parse le HTML d'une page de post Instagram et extrait
    author, caption (via og:description), et le premier commentaire
    écrit par l'auteur du post (= 'pinned' au sens demandé)."""
    soup = BeautifulSoup(html, "html.parser")
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    caption = og_desc["content"] if og_desc and og_desc.get("content") else ""

    article = soup.find("article")
    author: Optional[str] = None
    pinned: Optional[str] = None
    if article:
        header = article.find("header")
        if header:
            a = header.find("a", href=True)
            if a:
                author = a.get_text(strip=True) or a["href"].strip("/").split("/")[0]
        if author:
            for li in article.find_all("li"):
                a = li.find("a", href=True)
                if not a:
                    continue
                username = a.get_text(strip=True) or a["href"].strip("/").split("/")[0]
                if username == author:
                    span = li.find("span")
                    if span:
                        pinned = span.get_text(" ", strip=True)
                        break
    return {"author": author, "caption": caption, "pinned_comment": pinned}


def fetch_post(shortcode: str, state_path: Path) -> dict:
    """Charge la page d'un post avec session authentifiée puis renvoie
    le dict {author, caption, pinned_comment, url}."""
    url = f"https://www.instagram.com/p/{shortcode}/"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        try:
            page.get_by_role("button", name="Load more comments").click(timeout=1500)
            page.wait_for_timeout(1000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    data = parse_post_html(html)
    data["url"] = url
    return data
