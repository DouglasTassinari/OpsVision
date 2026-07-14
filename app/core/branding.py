"""Identidade visual TAZZIN: logo, favicon e cores compartilhadas.

As cores são as do manual da marca (docs/marca/). O tema global (fundo,
fonte Poppins, cor primária) fica em .streamlit/config.toml; aqui entra o
que o tema não cobre: logo na sidebar, favicon e as cores das séries dos
gráficos, que por padrão ignoram a cor primária.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

LOGO_FULL = str(_ASSETS_DIR / "logo_full.png")
LOGO_WORDMARK = str(_ASSETS_DIR / "logo_wordmark.png")
LOGO_ICON = str(_ASSETS_DIR / "logo_icon.png")
FAVICON = str(_ASSETS_DIR / "favicon.png")

# Paleta oficial da marca.
MARINHO = "#0D1B2A"      # Confiança, estabilidade — o fundo do sistema
VERDE = "#4CAF50"        # Crescimento, evolução — ação e destaque
CINZA_CLARO = "#F2F4F7"  # Neutralidade, clareza — o texto sobre o escuro
CINZA_MEDIO = "#6B7280"  # Equilíbrio, apoio — informação secundária
GRAFITE = "#1F2937"      # Contraste — cards, sidebar, superfícies

# Tom claro do marinho. O verde da marca carrega o sentido de "positivo", então
# ele não serve como cor neutra de série: um gráfico de gastos todo verde diria
# ao leitor que está tudo bem. As séries sem carga semântica usam este azul.
AZUL = "#4A90D9"

CHART_COLOR = AZUL


def apply_branding(page_title: str) -> None:
    """Configura título, favicon e logo da página. Deve ser a primeira chamada st.*."""
    st.set_page_config(
        page_title=f"{page_title} · Sistema TAZZIN",
        page_icon=FAVICON,
        layout="wide",
    )
    st.logo(LOGO_WORDMARK, icon_image=LOGO_ICON, size="large")
    st.sidebar.image(LOGO_FULL, width="stretch")
