# How to run

## Requirements

- Python 3.11+

## 1. Install

```bash
cd OpsVision
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Create the schema and seed data

```bash
python scripts/generate_synthetic_data.py --reset
```

`--reset` drops and recreates every table first — safe to re-run any
time you want a fresh dataset. Omit it to add on top of an existing
database (will fail on unique-constraint collisions if run twice without
`--reset`, since codes/SKUs/order numbers are not re-randomized across
runs with the same `--seed`).

Options:

- `--seed <int>` — random seed, default `42`. Same seed → same dataset.
- `--reset` — drop and recreate all tables first.

This creates `data/tazzin.db` (SQLite) with ~46,000 rows across 38
tables, dated from 2023-01-01 to today. See
[`DATA_GENERATION.md`](DATA_GENERATION.md) for what gets generated and in
what order.

## 3. Run the app

```bash
streamlit run app/main.py
```

Opens the Dashboard at `http://localhost:8501`. Use the sidebar to reach
each module's page (Sales, Production, Inventory, Purchasing, Finance,
People, Projects, Maintenance, Quality, Administration).

## 4. Run tests

```bash
pytest                          # all 153 tests, ~3s
pytest tests/test_services/     # just service-layer tests
pytest -k sales                 # just the Sales module
```

## 5. Lint

```bash
ruff check app tests scripts
```

## 6. Health check (CLI)

```bash
python scripts/run_health_check.py
```

Prints database + filesystem probe results and exits with status 1 if
anything is unhealthy — wire this into a cron job or uptime monitor for
a real deployment.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `TAZZIN_DATABASE_URL` | `sqlite:///data/tazzin.db` | Any SQLAlchemy connection string, e.g. `postgresql://user:pass@host/tazzin` |
| `TAZZIN_ENV` | `development` | Free-text environment label |
| `TAZZIN_LOG_LEVEL` | `INFO` | Standard logging levels |
| `TAZZIN_LOG_FORMAT` | `json` | `json` or `text` |

Example, running against PostgreSQL instead of the bundled SQLite file:

```bash
export TAZZIN_DATABASE_URL="postgresql://tazzin:password@localhost/tazzin"
python scripts/generate_synthetic_data.py --reset
streamlit run app/main.py
```

No code changes are needed to switch backends — `app/database/base.py`
builds the engine from `TAZZIN_DATABASE_URL` alone.
