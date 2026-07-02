"""Sales dashboard page."""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path as _Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.database.base import session_scope
from app.services.sales_service import SalesService

st.title("Vendas")
st.caption("Receita, pipeline de pedidos e principais clientes.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = SalesService(session)
    revenue_rows = service.monthly_revenue(start, end)
    top_customers = service.top_customers(start, end, limit=10)

    revenue_df = pd.DataFrame(revenue_rows, columns=["Mês", "Receita Líquida"])
    customers_df = pd.DataFrame(top_customers, columns=["Cliente", "Total"])

    total_revenue = revenue_df["Receita Líquida"].sum() if not revenue_df.empty else 0
    active_customers = len(service.active_customers())

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Receita líquida no período", f"${total_revenue:,.0f}")
kpi2.metric("Clientes ativos", active_customers)
kpi3.metric("Meses com pedidos", len(revenue_df))

st.subheader("Receita por mês")
if revenue_df.empty:
    st.info("Nenhum pedido no período selecionado. Execute primeiro o gerador de dados sintéticos.")
else:
    st.line_chart(revenue_df.set_index("Mês"))

st.subheader("Top 10 clientes")
if customers_df.empty:
    st.info("Nenhum dado de cliente no período selecionado.")
else:
    st.bar_chart(customers_df.set_index("Cliente"))
