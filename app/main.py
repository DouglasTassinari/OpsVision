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

from app.core.bootstrap import ensure_demo_data
from app.database.base import session_scope
from app.services.analytics_service import AnalyticsService

st.set_page_config(page_title="OpsVision", page_icon="📊", layout="wide")


@st.cache_resource(show_spinner="Preparando o banco de dados de demonstração...")
def _bootstrap() -> bool:
    ensure_demo_data()
    return True


_bootstrap()

st.title("OpsVision")
st.caption("Plataforma de Inteligência Operacional Empresarial — visão executiva.")

col1, col2 = st.columns(2)
default_start = date.today() - timedelta(days=365)
start = col1.date_input("De", value=default_start, key="dash_start")
end = col2.date_input("Até", value=date.today(), key="dash_end")

with session_scope() as session:
    service = AnalyticsService(session)
    summary = service.executive_summary(start, end)
    revenue_rows = service.revenue_trend(start, end)
    cashflow_rows = service.cashflow_trend(start, end)

row1 = st.columns(4)
row1[0].metric("Receita", f"${summary['total_revenue']:,.0f}")
row1[1].metric("Gastos", f"${summary['total_spend']:,.0f}")
row1[2].metric("Fluxo de caixa líquido", f"${summary['net_cashflow']:,.0f}")
row1[3].metric("Projetos ativos", summary["active_projects"])

row2 = st.columns(4)
row2[0].metric("Rendimento médio de produção", f"{summary['avg_production_yield']:.1f}%")
row2[1].metric("Taxa média de defeitos", f"{summary['avg_defect_rate']:.1f}%")
row2[2].metric("Solicitações de manutenção abertas", summary["open_maintenance_requests"])
row2[3].metric("Quadro de funcionários ativo", summary["active_headcount"])

row3 = st.columns(2)
row3[0].metric("Contas a receber pendentes", f"${summary['outstanding_receivables']:,.0f}")
row3[1].metric("Contas a pagar pendentes", f"${summary['outstanding_payables']:,.0f}")

st.divider()

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.subheader("Receita por mês")
    revenue_df = pd.DataFrame(revenue_rows, columns=["Mês", "Receita"])
    if revenue_df.empty:
        st.info("Ainda não há dados de vendas. Execute primeiro o gerador de dados sintéticos.")
    else:
        st.line_chart(revenue_df.set_index("Mês"))

with chart_col2:
    st.subheader("Fluxo de caixa líquido por mês")
    cashflow_df = pd.DataFrame(cashflow_rows, columns=["Mês", "Fluxo de caixa líquido"])
    if cashflow_df.empty:
        st.info("Ainda não há dados financeiros. Execute primeiro o gerador de dados sintéticos.")
    else:
        st.line_chart(cashflow_df.set_index("Mês"))

st.divider()
st.caption(
    "Use a barra lateral para abrir Vendas, Produção, Estoque, Compras, Financeiro, "
    "Pessoas, Projetos, Manutenção, Qualidade e Administração."
)
