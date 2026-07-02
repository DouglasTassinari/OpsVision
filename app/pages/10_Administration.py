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

from app.database.base import session_scope
from app.services.administration_service import AdministrationService

st.title("Administration")
st.caption("Users, audit trail and system health.")

with session_scope() as session:
    service = AdministrationService(session)
    active_users = service.active_users()
    recent_events = service.recent_audit_events(limit=20)
    health = service.system_health()
    system_metrics = service.system_metrics()

    users_df = pd.DataFrame(
        [{"Username": u.username, "Email": u.email, "Active": u.is_active} for u in active_users]
    )
    events_df = pd.DataFrame(
        [
            {
                "When": e.occurred_at,
                "Action": e.action,
                "Entity": e.entity_name,
                "Entity ID": e.entity_id,
                "Detail": e.detail,
            }
            for e in recent_events
        ]
    )

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Active users", len(active_users))
kpi2.metric("System status", "Healthy" if health.healthy else "Degraded")
kpi3.metric("Uptime (s)", system_metrics["uptime_seconds"])

st.subheader("System health checks")
for check in health.checks:
    icon = "✅" if check.healthy else "❌"
    st.write(f"{icon} **{check.name}** — {check.detail} ({check.latency_ms} ms)")

st.subheader("Operation metrics")
if system_metrics["operations"]:
    metrics_df = pd.DataFrame(
        [
            {"Operation": name, "Calls": stats["count"], "Avg (ms)": stats["avg_ms"], "Errors": stats["errors"]}
            for name, stats in system_metrics["operations"].items()
        ]
    ).sort_values("Calls", ascending=False)
    st.dataframe(metrics_df, width="stretch")
else:
    st.info("No tracked operations yet — browse other pages to generate metrics.")

st.subheader("Active users")
if users_df.empty:
    st.info("No active users yet.")
else:
    st.dataframe(users_df, width="stretch")

st.subheader("Recent audit events")
if events_df.empty:
    st.info("No audit events recorded yet.")
else:
    st.dataframe(events_df, width="stretch")
