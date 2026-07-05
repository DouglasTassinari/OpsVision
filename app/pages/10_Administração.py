"""Administration page: users, audit trail and system observability."""
# ruff: noqa: E402  -- sys.path bootstrap below must run before the app.* imports
from __future__ import annotations

import sys
from pathlib import Path as _Path

# Streamlit only adds this script's own folder to sys.path, not the project
# root, so the "app.*" imports below would fail without this.
_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import streamlit as st

from app.core.bootstrap import ensure_demo_data_once
from app.core.branding import apply_branding
from app.database.base import session_scope
from app.services.administration_service import AdministrationService

apply_branding("Administração")

ensure_demo_data_once()

st.title("Administração")
st.caption("Usuários, trilha de auditoria e saúde do sistema.")

with session_scope() as session:
    service = AdministrationService(session)
    active_users = service.active_users()
    recent_events = service.recent_audit_events(limit=20)
    health = service.system_health()
    system_metrics = service.system_metrics()

    users_df = pd.DataFrame(
        [{"Usuário": u.username, "E-mail": u.email, "Ativo": u.is_active} for u in active_users]
    )
    events_df = pd.DataFrame(
        [
            {
                "Quando": e.occurred_at,
                "Ação": e.action,
                "Entidade": e.entity_name,
                "ID da Entidade": e.entity_id,
                "Detalhe": e.detail,
            }
            for e in recent_events
        ]
    )

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Usuários ativos", len(active_users))
kpi2.metric("Status do sistema", "Saudável" if health.healthy else "Degradado")
kpi3.metric("Tempo ativo (s)", system_metrics["uptime_seconds"])

st.subheader("Verificações de saúde do sistema")
for check in health.checks:
    icon = "✅" if check.healthy else "❌"
    st.write(f"{icon} **{check.name}** — {check.detail} ({check.latency_ms} ms)")

st.subheader("Métricas de operação")
if system_metrics["operations"]:
    metrics_df = pd.DataFrame(
        [
            {"Operação": name, "Chamadas": stats["count"], "Média (ms)": stats["avg_ms"], "Erros": stats["errors"]}
            for name, stats in system_metrics["operations"].items()
        ]
    ).sort_values("Chamadas", ascending=False)
    st.dataframe(metrics_df, width="stretch")
else:
    st.info("Nenhuma operação registrada ainda — navegue por outras páginas para gerar métricas.")

st.subheader("Usuários ativos")
if users_df.empty:
    st.info("Nenhum usuário ativo ainda.")
else:
    st.dataframe(users_df, width="stretch")

st.subheader("Eventos de auditoria recentes")
if events_df.empty:
    st.info("Nenhum evento de auditoria registrado ainda.")
else:
    st.dataframe(events_df, width="stretch")
