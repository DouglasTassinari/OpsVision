"""Quality dashboard page."""
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
from app.services.quality_service import QualityService

st.title("Qualidade")
st.caption("Taxas de defeito de inspeção, não conformidades e taxa de aprovação.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = QualityService(session)
    defect_rate_rows = service.defect_rate_trend(start, end)
    severity_rows = service.open_nonconformances_by_severity()
    pass_rate = service.pass_rate(start, end)

    defect_rate_df = pd.DataFrame(defect_rate_rows, columns=["Mês", "Taxa de Defeito %"])
    severity_df = pd.DataFrame(severity_rows, columns=["Severidade", "Quantidade Aberta"])

    avg_defect_rate = defect_rate_df["Taxa de Defeito %"].mean() if not defect_rate_df.empty else 0
    open_nonconformances = int(severity_df["Quantidade Aberta"].sum()) if not severity_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Taxa média de defeitos no período", f"{avg_defect_rate:.2f}%")
kpi2.metric("Não conformidades abertas", open_nonconformances)
kpi3.metric("Taxa de aprovação no período", f"{pass_rate:.2f}%")

st.subheader("Taxa de defeito por mês")
if defect_rate_df.empty:
    st.info("Nenhuma inspeção no período selecionado. Execute primeiro o gerador de dados sintéticos.")
else:
    st.line_chart(defect_rate_df.set_index("Mês"))

st.subheader("Não conformidades abertas por severidade")
if severity_df.empty:
    st.info("Nenhuma não conformidade aberta.")
else:
    st.bar_chart(severity_df.set_index("Severidade"))
