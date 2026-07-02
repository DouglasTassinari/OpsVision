"""Production dashboard page."""
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
from app.services.production_service import ProductionService

st.title("Produção")
st.caption("Vazão de ordens de produção, rendimento de linha e tendências de refugo.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = ProductionService(session)
    work_orders = service.work_orders.work_orders_between(start, end)
    yield_rows = service.line_yield_report(start, end)
    scrap_rows = service.monthly_scrap(start, end)

    yield_df = pd.DataFrame(yield_rows, columns=["Linha de Produção", "Rendimento Médio %"])
    scrap_df = pd.DataFrame(scrap_rows, columns=["Mês", "Unidades de Refugo"])

    total_work_orders = len(work_orders)
    avg_yield = yield_df["Rendimento Médio %"].mean() if not yield_df.empty else 0
    total_scrap = scrap_df["Unidades de Refugo"].sum() if not scrap_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Ordens de produção no período", total_work_orders)
kpi2.metric("Rendimento médio", f"{avg_yield:.1f}%")
kpi3.metric("Unidades de refugo no período", f"{total_scrap:,.0f}")

st.subheader("Rendimento por linha de produção")
if yield_df.empty:
    st.info("Nenhuma ordem de produção concluída no período selecionado. Execute primeiro o gerador de dados sintéticos.")
else:
    st.bar_chart(yield_df.set_index("Linha de Produção"))

st.subheader("Refugo por mês")
if scrap_df.empty:
    st.info("Nenhum dado de ordem de produção no período selecionado.")
else:
    st.line_chart(scrap_df.set_index("Mês"))
