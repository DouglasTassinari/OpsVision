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

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.core.formatting import format_brl
from app.database.base import session_scope
from app.services.finance_service import FinanceService

apply_branding("Financeiro")

ensure_demo_data_once()

DIRECOES = {"receivable": "A receber", "payable": "A pagar"}
STATUS_FATURA = {
    "paid": ("Pagas", charts.POSITIVO),
    "open": ("Abertas", "#A7A7AD"),
    "overdue": ("Vencidas", charts.NEGATIVO),
}

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
    breakdown = service.invoice_breakdown()

net_cashflow_total = sum(v for _, v in cashflow_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Contas a receber pendentes", format_brl(summary["receivables"]))
kpi2.metric("Contas a pagar pendentes", format_brl(summary["payables"]))
kpi3.metric("Fluxo de caixa líquido no período", format_brl(net_cashflow_total))

st.subheader("O caixa está saudável?")
if not cashflow_rows:
    st.info("Nenhuma transação no período selecionado.")
else:
    months, values = zip(*cashflow_rows)
    charts.render(charts.cashflow(months, values))
    st.caption(
        "Barras verdes = meses em que entrou mais do que saiu; vermelhas = o contrário. "
        "A linha pontilhada mostra o saldo acumulado no período."
    )

st.subheader("Faturas por situação")
if not breakdown:
    st.info("Nenhuma fatura registrada ainda.")
else:
    amounts = {(direction, status): total for direction, status, total in breakdown}
    directions = ["receivable", "payable"]
    series = {
        label: ([amounts.get((d, key), 0) for d in directions], color)
        for key, (label, color) in STATUS_FATURA.items()
    }
    charts.render(charts.stacked_hbar([DIRECOES[d] for d in directions], series, money=True))
    st.caption("Verde já virou caixa; cinza aguarda vencimento; vermelho está vencido e exige cobrança ou pagamento imediato.")
