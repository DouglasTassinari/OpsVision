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

import pandas as pd
import streamlit as st

from app.database.base import session_scope
from app.services.projects_service import ProjectsService

st.title("Projects")
st.caption("Delivery status, task completion and upcoming milestones.")

with session_scope() as session:
    service = ProjectsService(session)
    health_rows = service.project_health_report()
    upcoming = service.upcoming_milestones(date.today(), limit=50)
    upcoming_30d = [m for m in upcoming if m.due_date <= date.today() + timedelta(days=30)]

    health_df = pd.DataFrame(health_rows)

    active_count = len(health_rows)
    avg_completion = health_df["completion_rate"].mean() if not health_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Active projects", active_count)
kpi2.metric("Avg completion rate", f"{avg_completion:,.1f}%")
kpi3.metric("Milestones due in 30 days", len(upcoming_30d))

st.subheader("Completion rate by project")
if health_df.empty:
    st.info("No active projects. Run the synthetic data generator first.")
else:
    st.bar_chart(health_df.set_index("project")["completion_rate"])
