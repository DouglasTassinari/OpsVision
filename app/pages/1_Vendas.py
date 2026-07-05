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

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.core.formatting import format_brl
from app.database.base import session_scope
from app.services.sales_service import SalesService

apply_branding("Vendas")

ensure_demo_data_once()

SEGMENTOS = {"retail": "Varejo", "wholesale": "Atacado", "enterprise": "Corporativo"}

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
    segment_rows = service.revenue_by_segment(start, end)
    active_customers = len(service.active_customers())

total_revenue = sum(v for _, v in revenue_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Receita líquida no período", format_brl(total_revenue))
kpi2.metric("Clientes ativos", active_customers)
kpi3.metric("Meses com pedidos", len(revenue_rows))

trend_col, segment_col = st.columns([3, 2])
with trend_col:
    st.subheader("Evolução da receita")
    if not revenue_rows:
        st.info("Nenhum pedido no período selecionado.")
    else:
        months, values = zip(*revenue_rows)
        charts.render(charts.area(months, values, money=True))
        st.caption("Receita líquida faturada mês a mês no período selecionado.")

with segment_col:
    st.subheader("Quem gera a receita?")
    if not segment_rows:
        st.info("Nenhum dado de segmento no período selecionado.")
    else:
        labels = [SEGMENTOS.get(seg, seg.title()) for seg, _ in segment_rows]
        values = [total for _, total in segment_rows]
        charts.render(charts.donut(labels, values, money=True))
        st.caption("Participação de cada perfil de cliente na receita do período.")

st.subheader("Top 10 clientes")
if not top_customers:
    st.info("Nenhum dado de cliente no período selecionado.")
else:
    names, totals = zip(*top_customers)
    charts.render(charts.hbar(names, totals, money=True))
    st.caption("Maiores clientes por receita no período — concentração alta indica dependência.")
