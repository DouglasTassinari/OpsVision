"""Finance dashboard page."""
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
from app.services.finance_service import FinanceService

st.title("Finance")
st.caption("Receivables, payables and cash position.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("From", value=default_start)
end = col2.date_input("To", value=date.today())

with session_scope() as session:
    service = FinanceService(session)
    summary = service.outstanding_summary()
    cashflow_rows = service.cash_position(start, end)

    cashflow_df = pd.DataFrame(cashflow_rows, columns=["Month", "Net Cashflow"])
    net_cashflow_total = cashflow_df["Net Cashflow"].sum() if not cashflow_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Outstanding receivables", f"${summary['receivables']:,.0f}")
kpi2.metric("Outstanding payables", f"${summary['payables']:,.0f}")
kpi3.metric("Net cashflow in period", f"${net_cashflow_total:,.0f}")

st.subheader("Net cashflow by month")
if cashflow_df.empty:
    st.info("No transactions in the selected period. Run the synthetic data generator first.")
else:
    st.line_chart(cashflow_df.set_index("Month"))
