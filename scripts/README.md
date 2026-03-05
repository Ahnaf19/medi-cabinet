# Scripts

Utility scripts for development and operations.

## Files

- **`seed_data.py`** — Populate the database with sample medicines, routines, cost entries, and drug interactions for demo/testing purposes.

## Usage

```bash
uv run python scripts/seed_data.py
```

Requires the database to be initialized first (`alembic upgrade head`).
