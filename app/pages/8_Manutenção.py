"""Maintenance dashboard page."""
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
from app.database.models.maintenance import AssetCriticality, MaintenanceStatus
from app.services.maintenance_service import MaintenanceService

apply_branding("Manutenção")

ensure_demo_data_once()

PRIORIDADES = {
    "urgent": ("Urgente", charts.NEGATIVO),
    "high": ("Alta", charts.BORDO_CLARO),
    "medium": ("Média", "#A7A7AD"),
    "low": ("Baixa", "#6E6E76"),
}

st.title("Manutenção")
st.caption("Conservação de ativos, backlog de solicitações e custo de manutenção.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = MaintenanceService(session)
    cost_rows = service.monthly_maintenance_cost(start, end)
    priority_rows = service.open_requests_by_priority()

    total_cost = sum(v for _, v in cost_rows)
    open_requests = sum(
        len(service.requests.by_status(status))
        for status in (
            MaintenanceStatus.OPEN,
            MaintenanceStatus.SCHEDULED,
            MaintenanceStatus.IN_PROGRESS,
        )
    )
    critical_assets = len(service.assets.by_criticality(AssetCriticality.CRITICAL))

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Solicitações abertas", open_requests)
kpi2.metric("Custo de manutenção no período", format_brl(total_cost))
kpi3.metric("Ativos críticos", critical_assets)

cost_col, backlog_col = st.columns([3, 2])
with cost_col:
    st.subheader("Custo de manutenção por mês")
    if not cost_rows:
        st.info("Nenhum registro de manutenção no período selecionado.")
    else:
        months, values = zip(*cost_rows)
        charts.render(charts.area(months, values, money=True))
        st.caption("Gasto mensal com manutenção — alta contínua pode indicar ativos em fim de vida.")

with backlog_col:
    st.subheader("Backlog por prioridade")
    if not priority_rows:
        st.info("Nenhuma solicitação de manutenção aberta.")
    else:
        by_priority = dict(priority_rows)
        items = [
            (label, by_priority[key], color)
            for key, (label, color) in PRIORIDADES.items()
            if key in by_priority
        ]
        charts.render(
            charts.hbar(
                [i[0] for i in items], [i[1] for i in items], colors=[i[2] for i in items]
            )
        )
        st.caption("Solicitações abertas: vermelho = urgente, deve ser tratado primeiro.")
