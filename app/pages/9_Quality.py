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

st.title("Quality")
st.caption("Inspection defect rates, nonconformances and pass rate.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start)
end = col2.date_input("To", value=date.today())

with session_scope() as session:
    service = QualityService(session)
    defect_rate_rows = service.defect_rate_trend(start, end)
    severity_rows = service.open_nonconformances_by_severity()
    pass_rate = service.pass_rate(start, end)

    defect_rate_df = pd.DataFrame(defect_rate_rows, columns=["Month", "Defect Rate %"])
    severity_df = pd.DataFrame(severity_rows, columns=["Severity", "Open Count"])

    avg_defect_rate = defect_rate_df["Defect Rate %"].mean() if not defect_rate_df.empty else 0
    open_nonconformances = int(severity_df["Open Count"].sum()) if not severity_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Average defect rate in period", f"{avg_defect_rate:.2f}%")
kpi2.metric("Open nonconformances", open_nonconformances)
kpi3.metric("Pass rate in period", f"{pass_rate:.2f}%")

st.subheader("Defect rate by month")
if defect_rate_df.empty:
    st.info("No inspections in the selected period. Run the synthetic data generator first.")
else:
    st.line_chart(defect_rate_df.set_index("Month"))

st.subheader("Open nonconformances by severity")
if severity_df.empty:
    st.info("No open nonconformances.")
else:
    st.bar_chart(severity_df.set_index("Severity"))
