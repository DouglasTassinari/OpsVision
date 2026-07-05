"""Inventory dashboard page."""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path as _Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.database.base import session_scope
from app.services.inventory_service import InventoryService

apply_branding("Estoque")

ensure_demo_data_once()

CATEGORIAS = {
    "raw_material": "Matéria-prima",
    "component": "Componentes",
    "finished_good": "Produto acabado",
    "packaging": "Embalagens",
}

st.title("Estoque")
st.caption("Níveis de estoque disponível e alertas de reposição.")

with session_scope() as session:
    service = InventoryService(session)
    on_hand_rows = service.on_hand_report()
    category_rows = service.on_hand_by_category()
    low_stock = service.low_stock_alert()

total_active_skus = len(on_hand_rows)
total_units = sum(units for _, _, units in on_hand_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("SKUs ativos", total_active_skus)
kpi2.metric("Produtos com estoque baixo", len(low_stock))
kpi3.metric("Total de unidades em estoque", f"{total_units:,.0f}".replace(",", "."))

st.subheader("Onde está o estoque?")
if not category_rows:
    st.info("Nenhum produto com estoque positivo. Execute primeiro o gerador de dados sintéticos.")
else:
    tuples = [(CATEGORIAS.get(cat, cat.title()), name, units) for cat, name, units in category_rows]
    charts.render(charts.treemap(tuples))
    st.caption(
        "Cada retângulo é um produto e o tamanho é a quantidade em estoque, "
        "agrupado por categoria — áreas grandes concentram capital parado."
    )

st.subheader("Top 15 produtos por quantidade em estoque")
if not on_hand_rows:
    st.info("Nenhum produto ativo encontrado.")
else:
    top15 = sorted(on_hand_rows, key=lambda row: row[2], reverse=True)[:15]
    charts.render(charts.hbar([name for _, name, _ in top15], [units for _, _, units in top15]))
    st.caption("Produtos com maior volume físico em estoque.")
