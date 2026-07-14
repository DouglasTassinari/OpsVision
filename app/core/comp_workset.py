"""Session working-set for Compensation — the ephemeral write layer.

The Compensation module never persists user edits to the database. Instead, the
first access in a browser session loads a snapshot of the synthetic base into
``st.session_state`` (server-side, per-session memory). Every tab reads from — and,
in Phase 2, writes to — that working-set. A browser reload (F5) starts a fresh
session, ``st.session_state`` is empty, and the base is reloaded: no visitor's
simulation ever dirties the shared data.

This is the only place in the module that touches Streamlit; the domain and
repository layers stay pure and database-only.
"""
from __future__ import annotations

import streamlit as st

from app.database.base import session_scope
from app.services.compensation_service import CompensationSnapshot, CompensationService

_STATE_KEY = "comp_workset"


def get_workset() -> CompensationSnapshot:
    """Return this session's working-set, loading the base on first use."""
    if _STATE_KEY not in st.session_state:
        with session_scope() as session:
            st.session_state[_STATE_KEY] = CompensationService(session).load_snapshot()
    return st.session_state[_STATE_KEY]


def reset_workset() -> None:
    """Discard the session's edits and reload the base (same effect as F5)."""
    st.session_state.pop(_STATE_KEY, None)
