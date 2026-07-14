"""Import every model module so ``Base.metadata`` sees the full schema.

:mod:`scripts.init_db` and the test fixtures both do
``from app.database.models import *`` (indirectly, via this import)
before calling ``Base.metadata.create_all``.
"""
from app.database.models import (  # noqa: F401
    adjustments,
    administration,
    compensation,
    core,
    finance,
    inventory,
    machining,
    maintenance,
    people,
    production,
    projects,
    purchasing,
    quality,
    sales,
    scrap,
)
