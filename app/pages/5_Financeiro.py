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

st.title("Financeiro")
st.caption("Contas a receber, contas a pagar e posição de caixa.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start)
end = col2.date_input("Até", value=date.today())

with session_scope() as session:
    service = FinanceService(session)
    summary = service.outstanding_summary()
    cashflow_rows = service.cash_position(start, end)

    cashflow_df = pd.DataFrame(cashflow_rows, columns=["Mês", "Fluxo de Caixa Líquido"])
    net_cashflow_total = cashflow_df["Fluxo de Caixa Líquido"].sum() if not cashflow_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Contas a receber pendentes", f"${summary['receivables']:,.0f}")
kpi2.metric("Contas a pagar pendentes", f"${summary['payables']:,.0f}")
kpi3.metric("Fluxo de caixa líquido no período", f"${net_cashflow_total:,.0f}")

st.subheader("Fluxo de caixa líquido por mês")
if cashflow_df.empty:
    st.info("Nenhuma transação no período selecionado. Execute primeiro o gerador de dados sintéticos.")
else:
    st.line_chart(cashflow_df.set_index("Mês"))
