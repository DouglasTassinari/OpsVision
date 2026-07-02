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

import pandas as pd
import streamlit as st

from app.database.base import session_scope
from app.services.inventory_service import InventoryService

st.title("Estoque")
st.caption("Níveis de estoque disponível e alertas de reposição.")

with session_scope() as session:
    service = InventoryService(session)
    on_hand_rows = service.on_hand_report()
    low_stock = service.low_stock_alert()

    on_hand_df = pd.DataFrame(on_hand_rows, columns=["SKU", "Produto", "Em Estoque"])
    total_active_skus = len(on_hand_df)
    total_units = on_hand_df["Em Estoque"].sum() if not on_hand_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("SKUs ativos", total_active_skus)
kpi2.metric("Produtos com estoque baixo", len(low_stock))
kpi3.metric("Total de unidades em estoque", f"{total_units:,.0f}")

st.subheader("Top 15 produtos por quantidade em estoque")
if on_hand_df.empty:
    st.info("Nenhum produto ativo encontrado. Execute primeiro o gerador de dados sintéticos.")
else:
    top15 = on_hand_df.sort_values("Em Estoque", ascending=False).head(15)
    st.bar_chart(top15.set_index("SKU")["Em Estoque"])
