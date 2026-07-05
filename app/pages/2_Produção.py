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

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.database.base import session_scope
from app.services.production_service import ProductionService

apply_branding("Produção")

ensure_demo_data_once()

META_RENDIMENTO = 95.0
STATUS_ORDEM = {
    "completed": ("Concluídas", charts.POSITIVO),
    "in_progress": ("Em andamento", charts.BORDO_CLARO),
    "planned": ("Planejadas", "#A7A7AD"),
    "cancelled": ("Canceladas", charts.NEGATIVO),
}

st.title("Produção")
st.caption("Vazão de ordens de produção, rendimento de linha e tendências de refugo.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = ProductionService(session)
    yield_rows = service.line_yield_report(start, end)
    scrap_rows = service.monthly_scrap(start, end)
    status_rows = service.status_breakdown(start, end)

total_work_orders = sum(count for _, count in status_rows)
avg_yield = sum(v for _, v in yield_rows) / len(yield_rows) if yield_rows else 0
total_scrap = sum(v for _, v in scrap_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Ordens de produção no período", total_work_orders)
kpi2.metric("Rendimento médio", f"{avg_yield:.1f}%")
kpi3.metric("Unidades de refugo no período", f"{total_scrap:,.0f}".replace(",", "."))

yield_col, status_col = st.columns([3, 2])
with yield_col:
    st.subheader(f"Rendimento por linha — meta {META_RENDIMENTO:.0f}%")
    if not yield_rows:
        st.info("Nenhuma ordem de produção concluída no período selecionado.")
    else:
        ordered = sorted(yield_rows, key=lambda row: row[1], reverse=True)
        names = [name for name, _ in ordered]
        values = [value for _, value in ordered]
        colors = [charts.POSITIVO if v >= META_RENDIMENTO else charts.NEGATIVO for v in values]
        charts.render(charts.hbar(names, values, colors=colors, suffix="%"))
        st.caption("Linhas verdes atingem a meta de rendimento; vermelhas exigem investigação.")

with status_col:
    st.subheader("Situação das ordens")
    if not status_rows:
        st.info("Nenhuma ordem de produção no período selecionado.")
    else:
        by_status = dict(status_rows)
        items = [(label, by_status[key], color) for key, (label, color) in STATUS_ORDEM.items() if key in by_status]
        charts.render(charts.donut([i[0] for i in items], [i[1] for i in items], colors=[i[2] for i in items]))
        st.caption("Distribuição das ordens do período por estágio do ciclo de produção.")

st.subheader("Refugo por mês")
if not scrap_rows:
    st.info("Nenhum dado de ordem de produção no período selecionado.")
else:
    months, values = zip(*scrap_rows)
    charts.render(charts.area(months, values))
    st.caption("Unidades perdidas por mês — tendência de alta indica problema de processo.")
