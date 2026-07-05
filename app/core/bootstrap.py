"""First-run bootstrap: create the schema and seed demo data when needed.

Called by the Streamlit entrypoint so cloud deployments (e.g. Streamlit
Community Cloud), which start without the gitignored SQLite file, come up
with a populated dashboard instead of empty pages. A database seeded by an
older generator (tracked via DATASET_VERSION in the dataset_meta table) is
dropped and reseeded, so data fixes reach deployments whose filesystem
survives a code push. A current, populated database is left untouched.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, text

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("bootstrap")


def _dataset_version(session) -> str | None:
    try:
        row = session.execute(
            text("SELECT value FROM dataset_meta WHERE key = 'dataset_version'")
        ).first()
    except Exception:
        return None  # dataset_meta table missing: dataset predates versioning
    return row[0] if row else None


def ensure_demo_data() -> None:
    import app.database.models  # noqa: F401 — registers every model on Base.metadata
    from app.database.base import Base, SessionLocal, engine
    from app.database.models.sales import Customer
    from scripts.generate_synthetic_data import DATASET_VERSION, run

    if settings.is_sqlite and engine.url.database:
        Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        has_data = session.execute(select(Customer.id).limit(1)).first() is not None
        version = _dataset_version(session)
    finally:
        session.close()

    if has_data and version == str(DATASET_VERSION):
        return

    if has_data:
        logger.info(
            "stale demo dataset detected (version %s, expected %s); reseeding",
            version,
            DATASET_VERSION,
        )
    else:
        logger.info("empty database detected; generating synthetic demo dataset")

    run(reset=True)
    logger.info("synthetic demo dataset generated")


def ensure_demo_data_once() -> None:
    """Streamlit-cached wrapper, safe to call at the top of every page.

    Pages are standalone scripts in Streamlit, so each one must trigger the
    bootstrap itself — a visitor may deep-link to a page before the home
    page has ever run. ``st.cache_resource`` makes this a no-op after the
    first call in the process.
    """
    import streamlit as st

    @st.cache_resource(show_spinner="Preparando o banco de dados de demonstração...")
    def _cached() -> bool:
        ensure_demo_data()
        return True

    _cached()
