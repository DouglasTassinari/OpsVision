"""Purchasing dashboard page."""
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
from app.services.purchasing_service import PurchasingService

apply_branding("Compras")

ensure_demo_data_once()

CATEGORIAS = {
    "raw_material": "Matéria-prima",
    "services": "Serviços",
    "equipment": "Equipamentos",
    "packaging": "Embalagens",
}

st.title("Compras")
st.caption("Gastos, pipeline de pedidos e principais fornecedores.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = PurchasingService(session)
    spend_rows = service.monthly_spend(start, end)
    top_suppliers = service.top_suppliers(start, end, limit=10)
    category_rows = service.spend_by_category(start, end)
    suppliers = service.suppliers.list()

    active_suppliers = len(suppliers)
    avg_rating = sum(float(s.rating) for s in suppliers) / len(suppliers) if suppliers else 0

total_spend = sum(v for _, v in spend_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gasto total no período", format_brl(total_spend))
kpi2.metric("Fornecedores ativos", active_suppliers)
kpi3.metric("Avaliação média de fornecedores", f"{avg_rating:.1f} / 5")

trend_col, gauge_col = st.columns([3, 2])
with trend_col:
    st.subheader("Evolução dos gastos")
    if not spend_rows:
        st.info("Nenhum pedido no período selecionado.")
    else:
        months, values = zip(*spend_rows)
        charts.render(charts.area(months, values, money=True))
        st.caption("Total comprado mês a mês — picos merecem conferência com o planejamento.")

with gauge_col:
    st.subheader("Qualidade da base de fornecedores")
    charts.render(charts.gauge(round(avg_rating, 1), max_value=5, target=4, suffix=""))
    st.caption("Avaliação média (0 a 5). A marca branca indica a meta: 4,0.")

rank_col, cat_col = st.columns([3, 2])
with rank_col:
    st.subheader("Top 10 fornecedores")
    if not top_suppliers:
        st.info("Nenhum dado de fornecedor no período selecionado.")
    else:
        names, totals = zip(*top_suppliers)
        charts.render(charts.hbar(names, totals, money=True))
        st.caption("Maiores fornecedores por volume comprado no período.")

with cat_col:
    st.subheader("Com o que gastamos?")
    if not category_rows:
        st.info("Nenhum dado de categoria no período selecionado.")
    else:
        labels = [CATEGORIAS.get(cat, cat.title()) for cat, _ in category_rows]
        values = [total for _, total in category_rows]
        charts.render(charts.donut(labels, values, money=True))
        st.caption("Distribuição do gasto por categoria de fornecimento.")
