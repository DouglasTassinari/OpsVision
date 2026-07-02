"""Sales dashboard page."""
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
from app.services.sales_service import SalesService

st.title("Sales")
st.caption("Revenue, order pipeline and top accounts.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start)
end = col2.date_input("To", value=date.today())

with session_scope() as session:
    service = SalesService(session)
    revenue_rows = service.monthly_revenue(start, end)
    top_customers = service.top_customers(start, end, limit=10)

    revenue_df = pd.DataFrame(revenue_rows, columns=["Month", "Net Revenue"])
    customers_df = pd.DataFrame(top_customers, columns=["Customer", "Total"])

    total_revenue = revenue_df["Net Revenue"].sum() if not revenue_df.empty else 0
    active_customers = len(service.active_customers())

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Net revenue in period", f"${total_revenue:,.0f}")
kpi2.metric("Active customers", active_customers)
kpi3.metric("Months with orders", len(revenue_df))

st.subheader("Revenue by month")
if revenue_df.empty:
    st.info("No orders in the selected period. Run the synthetic data generator first.")
else:
    st.line_chart(revenue_df.set_index("Month"))

st.subheader("Top 10 customers")
if customers_df.empty:
    st.info("No customer data in the selected period.")
else:
    st.bar_chart(customers_df.set_index("Customer"))
