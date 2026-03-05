# Tests

Pytest-based async test suite using in-memory SQLite.

## Structure

```
tests/
  conftest.py                          # Shared fixtures (in-memory DB, repos, sample data)
  test_database.py                     # Medicine + activity log repository tests
  test_parsers.py                      # Add/use/search/list parser tests
  test_llm/
    test_factory.py                    # Provider factory registration and creation
    test_providers.py                  # Provider properties and message formatting
    test_llm_parser.py                 # Tier 2 LLM parser with mock provider
  test_services/
    test_routine_service.py            # Routine + routine log repository tests
    test_interaction_service.py        # Drug interaction repository tests
    test_analytics_service.py          # Cost repository tests
```

## Running

```bash
uv run pytest                          # All tests
uv run pytest -v                       # Verbose
uv run pytest --cov=src                # With coverage
uv run pytest tests/test_parsers.py    # Specific file
```

## Fixtures

All database tests use an in-memory SQLite instance via the `test_db` fixture in `conftest.py`. Repository fixtures (`medicine_repo`, `routine_repo`, etc.) are session-scoped for performance.
