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


def parse_post_media(html: str) -> dict:
    """Détecte le type média d'une page de post Instagram.

    Renvoie {is_video: bool, image_urls: list[str]}. Pour un carrousel,
    le HTML statique n'expose souvent que la 1re image (og:image) ; les
    slides suivantes sont collectées par fetch_post via Playwright."""
    soup = BeautifulSoup(html, "html.parser")
    og_type = soup.find("meta", attrs={"property": "og:type"})
    og_video = soup.find("meta", attrs={"property": "og:video"})
    type_val = (og_type["content"] if og_type and og_type.get("content") else "").lower()
    is_video = bool(og_video) or "video" in type_val

    image_urls: list[str] = []
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        image_urls.append(og_image["content"])
    return {"is_video": is_video, "image_urls": image_urls}


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
        media = parse_post_media(html)
        image_urls = list(media["image_urls"])
        if not media["is_video"]:
            # Carrousel : cliquer "Suivant" pour charger chaque slide. On ne
            # collecte que les images DANS le conteneur carrousel pour éviter
            # les avatars, vignettes de posts suggérés et avatars de commentaires.
            # Les posts mono-image n'ont pas de conteneur carrousel : og:image
            # (déjà dans image_urls) sert de socle.
            for _ in range(20):  # garde-fou anti-boucle
                for img in page.query_selector_all("[aria-roledescription='carousel'] img"):
                    src = img.get_attribute("src")
                    if src and src.startswith("http") and src not in image_urls:
                        image_urls.append(src)
                nxt = page.query_selector(
                    "[aria-roledescription='carousel'] button[aria-label='Next'], "
                    "[aria-roledescription='carousel'] button[aria-label='Suivant']"
                )
                if not nxt:
                    break
                try:
                    nxt.click(timeout=1000)
                    page.wait_for_timeout(600)
                except Exception:
                    break
        browser.close()
    data = parse_post_html(html)
    data["url"] = url
    data["is_video"] = media["is_video"]
    data["image_urls"] = image_urls
    return data
