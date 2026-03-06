# Database Migrations

Alembic-managed SQLite schema migrations.

## Versions

| Version | Description |
|---------|-------------|
| `001_initial_schema` | `medicines` + `activity_log` tables |
| `002_add_routines` | `routines` + `routine_logs` tables |
| `003_add_drug_interactions` | `drug_interactions` table |
| `004_add_cost_tracking` | `medicine_costs` table |

## Commands

```bash
alembic upgrade head          # Apply all pending migrations
alembic downgrade -1          # Rollback last migration
alembic history               # View migration history
alembic current               # Show current revision
```

## Creating a New Migration

```bash
alembic revision -m "description"
```

Then edit the generated file in `versions/` to add `upgrade()` and `downgrade()` functions.
