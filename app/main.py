"""OpsVision entrypoint: registra as páginas e roteia a navegação.

Execute via ``streamlit run app/main.py``. Os títulos exibidos na
navegação vêm daqui (st.Page), não dos nomes dos arquivos — o que
permite nomes em português com acento sem afetar o caminho do
entrypoint esperado por deploys (ex.: Streamlit Community Cloud).
"""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

pages = [
    st.Page("Início.py", title="Início", icon=":material/home:", default=True),
    st.Page("pages/1_Vendas.py", title="Vendas", icon=":material/sell:", url_path="vendas"),
    st.Page("pages/2_Produção.py", title="Produção", icon=":material/factory:", url_path="producao"),
    st.Page("pages/3_Estoque.py", title="Estoque", icon=":material/inventory_2:", url_path="estoque"),
    st.Page("pages/4_Compras.py", title="Compras", icon=":material/shopping_cart:", url_path="compras"),
    st.Page("pages/5_Financeiro.py", title="Financeiro", icon=":material/payments:", url_path="financeiro"),
    st.Page("pages/6_Pessoas.py", title="Pessoas", icon=":material/group:", url_path="pessoas"),
    st.Page("pages/7_Projetos.py", title="Projetos", icon=":material/folder_open:", url_path="projetos"),
    st.Page("pages/8_Manutenção.py", title="Manutenção", icon=":material/build:", url_path="manutencao"),
    st.Page("pages/9_Qualidade.py", title="Qualidade", icon=":material/verified:", url_path="qualidade"),
    st.Page(
        "pages/10_Administração.py",
        title="Administração",
        icon=":material/admin_panel_settings:",
        url_path="administracao",
    ),
]

st.navigation(pages).run()
