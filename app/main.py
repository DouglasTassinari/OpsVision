"""OpsVision entrypoint: executive Dashboard (run via ``streamlit run app/main.py``)."""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.database.base import session_scope
from app.services.analytics_service import AnalyticsService

st.set_page_config(page_title="OpsVision", page_icon="📊", layout="wide")

st.title("OpsVision")
st.caption("Enterprise Operations Intelligence Platform — executive overview.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start, key="dash_start")
end = col2.date_input("To", value=date.today(), key="dash_end")

with session_scope() as session:
    service = AnalyticsService(session)
    summary = service.executive_summary(start, end)
    revenue_rows = service.revenue_trend(start, end)
    cashflow_rows = service.cashflow_trend(start, end)

row1 = st.columns(4)
row1[0].metric("Revenue", f"${summary['total_revenue']:,.0f}")
row1[1].metric("Spend", f"${summary['total_spend']:,.0f}")
row1[2].metric("Net cashflow", f"${summary['net_cashflow']:,.0f}")
row1[3].metric("Active projects", summary["active_projects"])

row2 = st.columns(4)
row2[0].metric("Avg production yield", f"{summary['avg_production_yield']:.1f}%")
row2[1].metric("Avg defect rate", f"{summary['avg_defect_rate']:.1f}%")
row2[2].metric("Open maintenance requests", summary["open_maintenance_requests"])
row2[3].metric("Active headcount", summary["active_headcount"])

row3 = st.columns(2)
row3[0].metric("Outstanding receivables", f"${summary['outstanding_receivables']:,.0f}")
row3[1].metric("Outstanding payables", f"${summary['outstanding_payables']:,.0f}")

st.divider()

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.subheader("Revenue by month")
    revenue_df = pd.DataFrame(revenue_rows, columns=["Month", "Revenue"])
    if revenue_df.empty:
        st.info("No sales data yet. Run the synthetic data generator first.")
    else:
        st.line_chart(revenue_df.set_index("Month"))

with chart_col2:
    st.subheader("Net cashflow by month")
    cashflow_df = pd.DataFrame(cashflow_rows, columns=["Month", "Net cashflow"])
    if cashflow_df.empty:
        st.info("No finance data yet. Run the synthetic data generator first.")
    else:
        st.line_chart(cashflow_df.set_index("Month"))

st.divider()
st.caption(
    "Use the sidebar to open Sales, Production, Inventory, Purchasing, Finance, "
    "People, Projects, Maintenance, Quality and Administration."
)
