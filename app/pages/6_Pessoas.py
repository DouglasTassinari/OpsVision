"""People dashboard page."""
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
from app.services.people_service import PeopleService

apply_branding("Pessoas")

ensure_demo_data_once()

st.title("Pessoas")
st.caption("Quadro de funcionários e utilização de folgas.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = PeopleService(session)
    headcount_rows = service.headcount_report()
    utilization_rows = service.time_off_utilization(start, end)
    pending_count = len(service.time_off.pending_requests())

active_headcount = sum(count for _, count in headcount_rows)
approved_days_in_period = sum(days for _, days in utilization_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Quadro de funcionários ativo", active_headcount)
kpi2.metric("Solicitações de folga pendentes", pending_count)
kpi3.metric("Dias aprovados no período", approved_days_in_period)

dept_col, timeoff_col = st.columns([3, 2])
with dept_col:
    st.subheader("Quadro por departamento")
    if not headcount_rows:
        st.info("Nenhum funcionário ativo ainda.")
    else:
        names, counts = zip(*headcount_rows)
        charts.render(charts.hbar(names, counts))
        st.caption("Funcionários ativos em cada departamento.")

with timeoff_col:
    st.subheader("Folgas ao longo do ano")
    if not utilization_rows:
        st.info("Nenhuma folga aprovada no período selecionado.")
    else:
        months, days = zip(*utilization_rows)
        charts.render(charts.area(months, days))
        st.caption("Dias de folga aprovados por mês — picos concentram ausências.")
