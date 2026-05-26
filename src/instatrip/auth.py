from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright
from rich.console import Console

console = Console()


def login_and_save_state(state_path: Path) -> None:
    """Ouvre Chromium en mode headed. L'utilisateur se connecte
    manuellement à Instagram puis appuie sur Entrée dans le terminal.
    L'état de session (cookies + localStorage) est sauvegardé."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/")
        console.print(
            "[yellow]→ Connecte-toi à Instagram dans la fenêtre, "
            "puis reviens ici et appuie sur Entrée."
        )
        input()
        context.storage_state(path=str(state_path))
        console.print(f"[green]✓ Session sauvegardée : {state_path}")
        browser.close()
