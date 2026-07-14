"""Create the Sistema TAZZIN schema without touching data.

Usage: python scripts/init_db.py [--reset]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.database.models  # noqa: F401 — registers every model on Base.metadata
from app.database.base import Base, engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Drop all tables before creating them")
    args = parser.parse_args()

    if args.reset:
        print("Dropping existing tables...")
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)
    print(f"Schema ready: {len(Base.metadata.tables)} tables at {engine.url}")


if __name__ == "__main__":
    main()
