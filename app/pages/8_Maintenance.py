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

from app.database.base import session_scope
from app.database.models.maintenance import AssetCriticality, MaintenanceStatus
from app.services.maintenance_service import MaintenanceService

st.title("Maintenance")
st.caption("Asset upkeep, request backlog and maintenance cost.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start)
end = col2.date_input("To", value=date.today())

with session_scope() as session:
    service = MaintenanceService(session)
    cost_rows = service.monthly_maintenance_cost(start, end)
    priority_rows = service.open_requests_by_priority()

    cost_df = pd.DataFrame(cost_rows, columns=["Month", "Cost"])
    priority_df = pd.DataFrame(priority_rows, columns=["Priority", "Open Requests"])

    total_cost = cost_df["Cost"].sum() if not cost_df.empty else 0
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
kpi1.metric("Open requests", open_requests)
kpi2.metric("Maintenance cost in period", f"${total_cost:,.0f}")
kpi3.metric("Critical assets", critical_assets)

st.subheader("Maintenance cost by month")
if cost_df.empty:
    st.info("No maintenance logs in the selected period. Run the synthetic data generator first.")
else:
    st.line_chart(cost_df.set_index("Month"))

st.subheader("Open requests by priority")
if priority_df.empty:
    st.info("No open maintenance requests.")
else:
    st.bar_chart(priority_df.set_index("Priority"))
