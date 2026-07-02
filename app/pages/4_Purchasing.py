"""Purchasing dashboard page."""
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
from app.services.purchasing_service import PurchasingService

st.title("Purchasing")
st.caption("Spend, order pipeline and top suppliers.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start)
end = col2.date_input("To", value=date.today())

with session_scope() as session:
    service = PurchasingService(session)
    spend_rows = service.monthly_spend(start, end)
    top_suppliers = service.top_suppliers(start, end, limit=10)
    suppliers = service.suppliers.list()

    spend_df = pd.DataFrame(spend_rows, columns=["Month", "Total Spend"])
    suppliers_df = pd.DataFrame(top_suppliers, columns=["Supplier", "Total"])

    total_spend = spend_df["Total Spend"].sum() if not spend_df.empty else 0
    active_suppliers = len(suppliers)
    avg_rating = (
        sum(float(s.rating) for s in suppliers) / len(suppliers) if suppliers else 0
    )

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Total spend in period", f"${total_spend:,.0f}")
kpi2.metric("Active suppliers", active_suppliers)
kpi3.metric("Average supplier rating", f"{avg_rating:.1f}")

st.subheader("Spend by month")
if spend_df.empty:
    st.info("No orders in the selected period. Run the synthetic data generator first.")
else:
    st.line_chart(spend_df.set_index("Month"))

st.subheader("Top 10 suppliers")
if suppliers_df.empty:
    st.info("No supplier data in the selected period.")
else:
    st.bar_chart(suppliers_df.set_index("Supplier"))
