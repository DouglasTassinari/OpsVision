"""Projects dashboard page."""
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
from app.services.projects_service import ProjectsService

apply_branding("Projetos")

ensure_demo_data_once()

STATUS_PROJETO = {
    "active": ("Ativos", charts.BORDO_CLARO),
    "planning": ("Em planejamento", "#A7A7AD"),
    "on_hold": ("Em espera", "#8C8C93"),
    "completed": ("Concluídos", charts.POSITIVO),
    "cancelled": ("Cancelados", charts.NEGATIVO),
}

st.title("Projetos")
st.caption("Status de entrega, conclusão de tarefas e próximos marcos.")

with session_scope() as session:
    service = ProjectsService(session)
    health_rows = service.project_health_report()
    status_rows = service.status_breakdown()
    upcoming = service.upcoming_milestones(date.today(), limit=50)
    upcoming_30d = [m for m in upcoming if m.due_date <= date.today() + timedelta(days=30)]

active_count = len(health_rows)
avg_completion = (
    sum(row["completion_rate"] for row in health_rows) / active_count if active_count else 0
)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Projetos ativos", active_count)
kpi2.metric("Taxa média de conclusão", f"{avg_completion:,.1f}%")
kpi3.metric("Marcos com vencimento em 30 dias", len(upcoming_30d))

progress_col, status_col = st.columns([3, 2])
with progress_col:
    st.subheader("Andamento dos projetos ativos")
    if not health_rows:
        st.info("Nenhum projeto ativo.")
    else:
        ordered = sorted(health_rows, key=lambda row: row["completion_rate"], reverse=True)
        names = [row["project"] for row in ordered]
        rates = [row["completion_rate"] for row in ordered]
        colors = [
            charts.POSITIVO if r >= 75 else ("#A7A7AD" if r >= 40 else charts.NEGATIVO)
            for r in rates
        ]
        charts.render(charts.hbar(names, rates, colors=colors, suffix="%"))
        st.caption(
            "Percentual de tarefas concluídas: verde ≥ 75%, cinza em ritmo normal, "
            "vermelho < 40% (atenção)."
        )

with status_col:
    st.subheader("Carteira por status")
    if not status_rows:
        st.info("Nenhum projeto cadastrado.")
    else:
        by_status = dict(status_rows)
        items = [
            (label, by_status[key], color)
            for key, (label, color) in STATUS_PROJETO.items()
            if key in by_status
        ]
        charts.render(
            charts.donut([i[0] for i in items], [i[1] for i in items], colors=[i[2] for i in items])
        )
        st.caption("Composição de toda a carteira de projetos da empresa.")
