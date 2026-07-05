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

import streamlit as st

from app.core import charts
from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.database.base import session_scope
from app.services.quality_service import QualityService

apply_branding("Qualidade")

ensure_demo_data_once()

META_DEFEITOS = 2.0
META_APROVACAO = 95.0
SEVERIDADES = {
    "critical": ("Crítica", charts.NEGATIVO),
    "major": ("Alta", charts.BORDO_CLARO),
    "minor": ("Menor", "#A7A7AD"),
}

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

avg_defect_rate = (
    sum(v for _, v in defect_rate_rows) / len(defect_rate_rows) if defect_rate_rows else 0
)
open_nonconformances = sum(count for _, count in severity_rows)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Taxa média de defeitos no período", f"{avg_defect_rate:.2f}%")
kpi2.metric("Não conformidades abertas", open_nonconformances)
kpi3.metric("Taxa de aprovação no período", f"{pass_rate:.2f}%")

defect_col, gauge_col = st.columns([3, 2])
with defect_col:
    st.subheader("Taxa de defeito por mês")
    if not defect_rate_rows:
        st.info("Nenhuma inspeção no período selecionado.")
    else:
        months, values = zip(*defect_rate_rows)
        charts.render(
            charts.line_with_target(months, values, target=META_DEFEITOS, target_label="Meta < 2%")
        )
        st.caption("Percentual de itens com defeito nas inspeções — abaixo da linha da meta é o esperado.")

with gauge_col:
    st.subheader("Taxa de aprovação")
    charts.render(charts.gauge(round(pass_rate, 1), max_value=100, target=META_APROVACAO))
    st.caption("Inspeções aprovadas de primeira. A marca branca indica a meta: 95%.")

st.subheader("Não conformidades abertas por severidade")
if not severity_rows:
    st.info("Nenhuma não conformidade aberta.")
else:
    by_severity = dict(severity_rows)
    items = [
        (label, by_severity[key], color)
        for key, (label, color) in SEVERIDADES.items()
        if key in by_severity
    ]
    charts.render(
        charts.donut([i[0] for i in items], [i[1] for i in items], colors=[i[2] for i in items])
    )
    st.caption("Vermelho = severidade crítica: risco direto ao cliente ou à operação.")
