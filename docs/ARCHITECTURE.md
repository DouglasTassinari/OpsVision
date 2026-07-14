# Architecture

## Layers

Sistema TAZZIN follows a strict one-way layered architecture:

```
Interface (Streamlit pages)
      ↓
Services            — orchestration: calls repositories, enforces domain rules, logs, tracks metrics
      ↓
Domain rules        — pure functions, no I/O, no SQLAlchemy imports
      ↓
Repositories         — SQLAlchemy queries, one class per aggregate root
      ↓
Database (SQLAlchemy models + engine/session)
```

A page never imports a repository or a model directly — only the service
for its module. A service never talks to another module's repository or
model directly — only that module's service (see Analytics below). This
keeps every module replaceable and independently testable: `tests/`
exercises domain rules and repositories with no service involved, and
services with no Streamlit involved.

### Why domain rules are a separate layer from services

Putting validation and status-transition logic in `app/domain/*_rules.py`
instead of inline in the service means:

- Rules are testable with plain Python objects — no database session
  needed (`tests/test_domain/` has no fixtures beyond raw values).
- Rules are reusable if a second interface is added later (a REST API,
  a CLI) without duplicating validation logic in each interface.
- Services stay focused on orchestration (what to persist, what to log,
  what to return) rather than mixing "is this allowed" with "how do I
  save it."

## Module boundaries

Each business module (Sales, Production, Inventory, ...) owns:

- its own SQLAlchemy models (`app/database/models/<module>.py`)
- its own repository classes (`app/repositories/<module>_repository.py`)
- its own domain rules (`app/domain/<module>_rules.py`)
- its own service (`app/services/<module>_service.py`)
- its own Streamlit page (`app/pages/N_<Module>.py`)

Cross-module references are **plain foreign-key id columns**, never
SQLAlchemy `relationship()` objects that reach into another module's
mapped classes. For example, `SalesOrderItem.product_id` is a foreign key
into `inventory_products`, but `SalesOrderItem` has no `.product`
relationship — if Sales code needs the product name, it asks the
Inventory service for it.

This is a deliberate low-coupling choice, not an oversight: it means any
module's schema can evolve without touching another module's mapped
classes, and any module's test suite can run without importing every
other module's model. Relationships *within* a module (e.g.
`Customer -> SalesOrder -> SalesOrderItem`) do use `relationship()` since
that cohesion is intentional and local.

### The Analytics exception

`AnalyticsService` (backing the Dashboard home page) is the one place
that composes multiple module services together — it exists specifically
to aggregate cross-module KPIs (revenue, spend, cashflow, yield, defect
rate, headcount, ...) into a single executive snapshot. It owns no tables
of its own. Every other service only calls its own module's repositories.

## Cross-cutting concerns (`app/core/`)

- **`config.py`** — a single frozen `Settings` dataclass sourced from
  environment variables (`TAZZIN_DATABASE_URL`, `TAZZIN_ENV`,
  `TAZZIN_LOG_LEVEL`, `TAZZIN_LOG_FORMAT`). No module reads
  `os.environ` directly outside this file.
- **`logging.py`** — every module calls `get_logger(__name__)`; logs are
  JSON-formatted by default, written to both stdout and a rotating file
  under `logs/`.
- **`exceptions.py`** — a small hierarchy (`TazzinError` →
  `DataAccessError` / `BusinessRuleError` → `EntityNotFoundError` /
  `ValidationError`) so the interface layer only needs to catch
  `TazzinError` to render a friendly message, regardless of which
  layer raised it.
- **`health.py`** — `run_health_checks()` probes the database connection
  and log-directory writability; used by both the Administration page and
  `scripts/run_health_check.py` (a CLI probe suitable for cron/uptime
  monitoring, exits 1 on failure).
- **`metrics.py`** — an in-process `MetricsRegistry` tracking call count,
  average latency and error count per operation. Every public service
  method is wrapped with `@track("<module>.<method>")`; the Administration
  page renders the live snapshot.

## Data layer

- SQLAlchemy 2.0 declarative models (`Mapped[...]` / `mapped_column`
  style) with one `Base` shared across all 31 tables
  (`app/database/base.py`).
- SQLite by default (zero-config demo, file at `data/tazzin.db`);
  set `TAZZIN_DATABASE_URL` to point at PostgreSQL or any other
  SQLAlchemy-supported backend for a production deployment — no code
  changes required, only the connection string.
- `app/repositories/base.py` provides `BaseRepository[ModelT]` (get,
  list, add, add_many, delete, count) so module repositories only add the
  domain-specific aggregate queries.

## Testing philosophy

- Every test runs against a fresh **in-memory SQLite database**
  (`tests/conftest.py`), created from the real `Base.metadata` — not
  mocks. This catches schema/FK mistakes that a mocked repository would
  hide, at the cost of a full `create_all()` per test (still sub-3-second
  for the whole 153-test suite).
- Domain rule tests take no fixtures beyond raw values — they're testing
  pure functions.
- Repository tests exercise the actual SQL (aggregations, joins,
  `strftime` grouping) against real rows, not query builders in isolation.
- Service tests go through the same public API the Streamlit pages use.
