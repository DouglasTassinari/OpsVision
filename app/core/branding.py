"""Identidade visual OpsVision: logo, favicon e cores compartilhadas.

As cores acompanham a paleta oficial (docs/identidade-visual/). O tema
global (fundo, fonte Poppins, cor primária) fica em .streamlit/config.toml;
aqui entra o que o tema não cobre: logo na sidebar, favicon e a cor das
séries dos gráficos nativos, que por padrão ignoram a cor primária.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

LOGO_FULL = str(_ASSETS_DIR / "logo_full.png")
LOGO_WORDMARK = str(_ASSETS_DIR / "logo_wordmark.png")
LOGO_ICON = str(_ASSETS_DIR / "logo_icon.png")

BORDO = "#7A1E2D"
BORDO_ESCURO = "#4B0F18"
CARVAO = "#0F0F12"
CINZA = "#2B2B31"
CINZA_CLARO = "#A7A7AD"
BRANCO = "#F5F5F7"

CHART_COLOR = BORDO


def apply_branding(page_title: str) -> None:
    """Configura título, favicon e logo da página. Deve ser a primeira chamada st.*."""
    st.set_page_config(
        page_title=f"{page_title} · OpsVision",
        page_icon=LOGO_ICON,
        layout="wide",
    )
    st.logo(LOGO_WORDMARK, icon_image=LOGO_ICON, size="large")
