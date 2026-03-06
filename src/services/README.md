# Service Layer

Business logic orchestration sitting between command handlers and repositories.

## Services

| Service | Purpose |
|---------|---------|
| `routine_service.py` | Routine CRUD, scheduler integration, stock deduction on "taken" |
| `interaction_service.py` | Drug interaction checks against cabinet, seed from JSON |
| `image_service.py` | Vision LLM extraction from medicine packet photos |
| `analytics_service.py` | Usage patterns, restock predictions, cost summaries |

## Design

- Services coordinate between multiple repositories (e.g., `RoutineService` uses `RoutineRepository` + `MedicineRepository` + `RoutineScheduler`)
- All methods are `async`
- Services receive repository instances via constructor (dependency injection)
- They never access the database directly — always through repository methods
