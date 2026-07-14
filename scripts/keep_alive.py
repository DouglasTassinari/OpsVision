"""Mantém o deploy do Streamlit Community Cloud acordado.

O Community Cloud hiberna apps sem visitas por ~12 horas, e um ping HTTP
simples não conta como visita — só uma sessão real de navegador (websocket)
conta. Este script abre o app em um Chromium headless, clica no botão de
despertar se o app estiver hibernando e mantém a sessão aberta por alguns
segundos. Executado pelo workflow .github/workflows/keep-alive.yml.

Uso:
    APP_URL=https://opsvision.streamlit.app python scripts/keep_alive.py
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://opsvision.streamlit.app")
WAKE_BUTTON_TEXTS = ["get this app back up", "app back up", "wake"]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        print(f"Abrindo {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(10_000)

        # App hibernando: clica no botão "Yes, get this app back up."
        for button in page.get_by_role("button").all():
            label = (button.text_content() or "").strip().lower()
            if any(text in label for text in WAKE_BUTTON_TEXTS):
                print(f"App hibernando — clicando em '{label}' para despertar.")
                button.click()
                page.wait_for_timeout(60_000)
                break

        # Mantém a sessão websocket aberta o bastante para contar como visita.
        page.wait_for_timeout(30_000)

        content = page.content().lower()
        browser.close()

        if "tazzin" in content or "stapp" in content or "streamlit" in content:
            print("Sessão concluída — app respondendo.")
            return 0
        print("Página carregou, mas o conteúdo do app não foi identificado.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
