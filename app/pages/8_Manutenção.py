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

import pandas as pd
import streamlit as st

from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import CHART_COLOR, apply_branding
from app.core.formatting import format_brl
from app.database.base import session_scope
from app.database.models.maintenance import AssetCriticality, MaintenanceStatus
from app.services.maintenance_service import MaintenanceService

apply_branding("Manutenção")

ensure_demo_data_once()

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

    cost_df = pd.DataFrame(cost_rows, columns=["Mês", "Custo"])
    priority_df = pd.DataFrame(priority_rows, columns=["Prioridade", "Solicitações Abertas"])

    total_cost = cost_df["Custo"].sum() if not cost_df.empty else 0
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

st.subheader("Custo de manutenção por mês")
if cost_df.empty:
    st.info("Nenhum registro de manutenção no período selecionado. Execute primeiro o gerador de dados sintéticos.")
else:
    st.line_chart(cost_df.set_index("Mês"), color=CHART_COLOR)

st.subheader("Solicitações abertas por prioridade")
if priority_df.empty:
    st.info("Nenhuma solicitação de manutenção aberta.")
else:
    st.bar_chart(priority_df.set_index("Prioridade"), color=CHART_COLOR)
