"""Central application configuration, sourced from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the Sistema TAZZIN.

    Defaults target a zero-config local demo (SQLite file under ``data/``).
    Set ``TAZZIN_DATABASE_URL`` to point at PostgreSQL or another
    SQLAlchemy-supported backend in production.
    """

    app_name: str = "Sistema TAZZIN"
    environment: str = field(default_factory=lambda: os.getenv("TAZZIN_ENV", "development"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "TAZZIN_DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'tazzin.db'}"
        )
    )
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")
    log_level: str = field(default_factory=lambda: os.getenv("TAZZIN_LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: os.getenv("TAZZIN_LOG_FORMAT", "json"))

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
