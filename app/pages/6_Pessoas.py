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

import pandas as pd
import streamlit as st

from app.database.base import session_scope
from app.services.people_service import PeopleService

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

    headcount_df = pd.DataFrame(headcount_rows, columns=["Departamento", "Funcionários Ativos"])
    utilization_df = pd.DataFrame(utilization_rows, columns=["Mês", "Dias Aprovados"])

    active_headcount = int(headcount_df["Funcionários Ativos"].sum()) if not headcount_df.empty else 0
    approved_days_in_period = int(utilization_df["Dias Aprovados"].sum()) if not utilization_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Quadro de funcionários ativo", active_headcount)
kpi2.metric("Solicitações de folga pendentes", pending_count)
kpi3.metric("Dias aprovados no período", approved_days_in_period)

st.subheader("Quadro de funcionários por departamento")
if headcount_df.empty:
    st.info("Nenhum funcionário ativo ainda. Execute primeiro o gerador de dados sintéticos.")
else:
    st.bar_chart(headcount_df.set_index("Departamento"))
