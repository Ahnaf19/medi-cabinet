# Medi-Cabinet Bot - Architecture Documentation

## 1. System Design

### 1.1 High-Level Architecture

The Medi-Cabinet Bot follows a clean, layered architecture designed for maintainability and extensibility:

```
┌─────────────────────────────────────────────────────┐
│                  Telegram API                         │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│              Bot Layer (bot.py)                       │
│  - Telegram handlers registration                    │
│  - Job scheduling (expiry checks, routine alarms)    │
│  - LLM provider & scheduler initialization           │
│  - Error handling                                    │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│         Command Layer (commands.py)                   │
│  - Route commands to handlers                        │
│  - Handle routines, costs, interactions, photos      │
│  - Tier 2 LLM fallback for ambiguous text            │
│  - Inline keyboard callbacks (Taken/Skip)            │
└──────┬────────────┬──────────────┬──────────────────┘
       │            │              │
       ▼            ▼              ▼
┌──────────┐  ┌──────────┐  ┌────────────┐
│ Parsers  │  │ Services │  │  Utilities │
│(Regex+LLM)│ │  Layer   │  │(Formatters)│
└──────────┘  └────┬─────┘  └────────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Database │ │   LLM    │ │Scheduler │
│  (Repos) │ │ Factory  │ │(JobQueue)│
└────┬─────┘ └────┬─────┘ └──────────┘
     │             │
     ▼             ▼
┌──────────┐ ┌──────────────┐
│  SQLite  │ │ Groq/OpenAI/ │
│ (6 tables)│ │  Anthropic   │
└──────────┘ └──────────────┘
```

### 1.2 Component Responsibilities

**Bot Layer** (`src/bot.py`)
- Initialize Telegram application
- Register command, message, photo, and callback handlers
- Setup scheduled jobs (expiry checks at 9 AM)
- Initialize LLM provider and routine scheduler at startup
- Configure logging with loguru
- Graceful startup and shutdown

**Command Layer** (`src/commands.py`)
- Handle user commands (`/start`, `/help`, `/delete`, `/stats`, `/routine`, `/cost`, `/costs`, `/interactions`, `/analytics`)
- Process natural text messages with multi-tier NLU
- Handle photo messages via vision LLM
- Inline keyboard callbacks for routine Taken/Skip actions
- Admin authorization checks

**Parser Layer** (`src/parsers.py`)
- Natural language understanding with regex patterns
- Command type detection (add, use, search, list, routine, cost, interactions, analytics)
- `RoutineCommandParser`: Time parsing (AM/PM, word-based), frequency, meal relation
- `CostCommandParser`: "cost Napa 50tk", "Napa cost 100 taka"
- Confidence scoring for ambiguous matches

**LLM Layer** (`src/llm/`)
- `BaseLLMProvider`: Abstract interface with `complete()` and `complete_with_vision()`
- `LLMProviderFactory`: Registry-based factory with auto-registration
- `LLMParser`: Tier 2 fallback using tool calling for structured extraction
- Providers: Groq (full), OpenAI, Anthropic (placeholders)
- All use raw `httpx` — no SDK dependencies

**Service Layer** (`src/services/`)
- `RoutineService`: CRUD + scheduler + stock deduction on "taken"
- `InteractionService`: Check new medicines against cabinet, seed from JSON
- `ImageService`: Vision LLM extraction from medicine packet photos
- `AnalyticsService`: Usage patterns, restock predictions, cost summaries

**Database Layer** (`src/database.py`)
- Repository pattern for clean data access (6 repositories)
- Entity dataclasses: Medicine, Activity, Routine, RoutineLog, DrugInteraction, MedicineCost
- Fuzzy name matching with fuzzywuzzy
- Multi-group isolation (critical for privacy)
- Transaction support for atomic operations

**Scheduler** (`src/scheduler.py`)
- `RoutineScheduler`: Integrates with python-telegram-bot `JobQueue`
- Loads active routines at startup, schedules `run_daily` per time slot
- Sends inline keyboard reminders (Taken/Skip), marks missed on timeout

**Utility Layer** (`src/utils.py`)
- Formatting functions (medicines, routines, interactions, costs, analytics, adherence)
- Validation helpers
- Keyboard builders for inline buttons
- Message templates (welcome, help)

## 2. Design Decisions

### 2.1 Why Telegram?

**Pros:**
- Zero app installation required - families already use it
- Native group chat support for family coordination
- Rich media capabilities (photos for future OCR)
- Bot API is well-documented and reliable
- Popular in Bangladesh and South Asia

**Cons:**
- Dependent on Telegram infrastructure
- Internet connection required

**Decision:** The pros significantly outweigh the cons for the target audience.

### 2.2 Why SQLite?

**Rationale:**
- **Embedded database** - No separate server to manage
- **ACID compliant** - Data integrity guarantees
- **Sufficient scale** - Can handle 100s of families easily
- **Easy backups** - Single file to backup
- **Zero configuration** - Works out of the box

**Limitations:**
- Limited concurrent writes (acceptable for family use case)
- Single machine deployment

**Migration Path:** If needed, can migrate to PostgreSQL with minimal code changes due to repository pattern.

### 2.3 Why Async Architecture?

**Rationale:**
- python-telegram-bot is async-first
- Better I/O performance for database and network operations
- Can handle multiple users simultaneously without blocking
- Aligns with modern Python best practices

**Implementation:**
- `aiosqlite` for async database operations
- `async/await` throughout the codebase
- Async context managers for resource cleanup

### 2.4 Parser Strategy

**Multi-Tier Approach:**

1. **Tier 1: Regex** (Fast, Deterministic, Free)
   - Priority-ordered patterns for each command type
   - Handle common variations (`+Napa 10`, `Bought Napa 10`)
   - Includes specialized parsers for routines and costs

2. **Fuzzy Matching** (Typo Tolerance)
   - Levenshtein distance with python-Levenshtein (C extension)
   - Confidence scoring (0-100)
   - Pre-filter by first letter for performance

3. **Tier 2: LLM Fallback** (When Configured)
   - Activates only when Tier 1 returns `unknown`
   - Uses tool calling via `MEDICINE_EXTRACTION_TOOL` for structured output
   - Maps LLM `ToolCall` → `ParsedCommand` with confidence=0.8
   - Graceful degradation: returns `None` on failure

**Why Not LLM-Only?**
- Regex is instant and deterministic
- No API costs for simple commands
- LLM is enhancement, not replacement — bot works fully without it

## 3. Database Schema Rationale

### 3.1 medicines Table

```sql
CREATE TABLE medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'tablets',
    expiry_date DATE NULL,
    location TEXT NULL,
    added_by_user_id INTEGER NOT NULL,
    added_by_username TEXT NOT NULL,  -- Denormalized for fast display
    added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    group_chat_id INTEGER NOT NULL,   -- Multi-tenancy isolation
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_chat_id, name COLLATE NOCASE)
);
```

**Design Choices:**
- `COLLATE NOCASE`: Case-insensitive name matching
- `added_by_username`: Denormalized for fast display (acceptable trade-off)
- `group_chat_id`: Multi-tenancy - each group sees only their data
- `UNIQUE(group_chat_id, name)`: Prevent duplicate medicines per group

**Indexes:**
```sql
-- Fast group + name lookups
CREATE INDEX idx_medicines_group_name ON medicines(group_chat_id, name COLLATE NOCASE);

-- Expiry date queries
CREATE INDEX idx_medicines_expiry ON medicines(expiry_date) WHERE expiry_date IS NOT NULL;

-- Low stock queries
CREATE INDEX idx_medicines_low_stock ON medicines(quantity) WHERE quantity < 3;
```

### 3.2 activity_log Table

```sql
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('added', 'used', 'searched', 'deleted')),
    quantity_change INTEGER NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    group_chat_id INTEGER NOT NULL,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
);
```

**Purpose:**
- **Audit trail**: Who did what and when
- **Usage analytics**: Most used medicines, most active users
- **Debugging**: Track down issues with user actions
- **Predictions**: Training data for restock predictions

### 3.3 routines & routine_logs Tables (Phase 4)

```sql
CREATE TABLE routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER REFERENCES medicines(id) ON DELETE SET NULL,
    medicine_name TEXT NOT NULL COLLATE NOCASE,
    dosage_quantity INTEGER DEFAULT 1,
    dosage_unit TEXT DEFAULT 'tablet',
    frequency TEXT DEFAULT 'daily',          -- daily/weekly/every_other_day/custom
    times_of_day TEXT NOT NULL DEFAULT '["08:00"]',  -- JSON array
    days_of_week TEXT,                       -- JSON array (for weekly)
    meal_relation TEXT,                      -- before_meal/after_meal/with_meal
    status TEXT DEFAULT 'active',            -- active/paused/completed
    created_by_user_id INTEGER NOT NULL,
    group_chat_id INTEGER NOT NULL,
    ...
);
```

### 3.4 drug_interactions Table (Phase 4)

```sql
CREATE TABLE drug_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a_name TEXT NOT NULL COLLATE NOCASE,
    drug_b_name TEXT NOT NULL COLLATE NOCASE,
    severity TEXT NOT NULL,                  -- mild/moderate/severe/contraindicated
    description TEXT,
    source TEXT,
    UNIQUE(drug_a_name, drug_b_name)
);
```

### 3.5 medicine_costs Table (Phase 5)

```sql
CREATE TABLE medicine_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL REFERENCES medicines(id) ON DELETE CASCADE,
    total_cost REAL NOT NULL,
    currency TEXT DEFAULT 'BDT',
    purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    group_chat_id INTEGER NOT NULL,
    ...
);
```

## 4. Scalability Considerations

### 4.1 Current Limits

- **Database**: SQLite handles ~100k medicines easily
- **Concurrent writes**: Limited but sufficient for family use
- **Storage**: Text-only data is negligible (< 1MB per family)

### 4.2 Scaling Strategy

**Vertical Scaling** (Current approach):
- Single machine can handle 1000s of families
- Increase CPU/RAM as needed

**Horizontal Scaling** (Future):
- Shard by `group_chat_id` to PostgreSQL
- Redis for caching (medicine name mappings)
- Queue system (Celery + Redis) for background jobs
- Load balancer for multiple bot instances

## 5. LLM Integration (Implemented)

### 5.1 Provider Factory Pattern

```python
# Providers self-register on import
LLMProviderFactory.register("groq", GroqProvider)

# Create from config (returns None if disabled)
provider = LLMProviderFactory.from_config(settings)

# Use for completions with tool calling
response = await provider.complete(messages, tools=[MEDICINE_EXTRACTION_TOOL])
```

### 5.2 Vision Processing Pipeline

```
Photo Message → Base64 encode → Vision LLM (Groq llama-3.2-90b-vision)
                                        ↓
                              Extract medicine info
                                        ↓
                              Confirm with user → Add to inventory
```

### 5.3 Drug Interaction Checking

```
Add Medicine → Check against cabinet → Query drug_interactions table
                                              ↓
                                    Display severity warnings
                                    (mild/moderate/severe/contraindicated)
```

**Data**: 30 pre-seeded interaction pairs for common BD medicines in `data/drug_interactions.json`.

## 6. Security Considerations

### 6.1 Token Management

- **Environment variables only** - Never commit `.env`
- **Rotation policy** - Change bot token periodically
- **Admin verification** - Admin commands check user ID

### 6.2 Data Privacy

- **No cloud storage** - All data stays on your server
- **Group isolation** - Strict `group_chat_id` filtering
- **Optional encryption** - Can add encryption at rest if needed

### 6.3 Input Validation

- **Sanitization**: Remove special characters from medicine names
- **SQL injection prevention**: Parameterized queries (automatic with aiosqlite)
- **Rate limiting**: Consider adding per-user/group limits

## 7. Error Handling Strategy

### 7.1 Error Levels

1. **User Errors** (Expected)
   - Friendly messages: "❌ Medicine not found"
   - Suggestions: "Try `?all` to see what's in the cabinet"

2. **System Errors** (Unexpected)
   - Log with correlation IDs (user_id, chat_id)
   - Generic user message: "⚠️ Something went wrong"
   - Alert admin for critical errors

3. **Critical Errors** (Fatal)
   - Log full stack trace
   - Graceful shutdown
   - Restart via systemd/Docker

### 7.2 Logging Strategy

```python
logger.bind(
    user_id=update.effective_user.id,
    chat_id=update.effective_chat.id,
    command=parsed_command.type
).info("Processing command", raw_text=update.message.text)
```

- **Structured logging** with loguru
- **Rotation**: 500 MB files, 10 days retention
- **Correlation IDs**: Track actions across logs
- **Sensitive data**: Redact tokens and personal info

## 8. Performance Optimizations

### 8.1 Database

- **Prepared statements**: Automatic with parameterized queries
- **Indexes**: Optimized for common queries
- **Connection reuse**: Single connection per request

### 8.2 Fuzzy Matching

```python
# Pre-filter by first letter
first_letter = query[0].lower()
candidates = [m for m in medicines if m.name[0].lower() == first_letter]
# Then apply expensive Levenshtein distance
```

- Reduces candidate set by ~96% (26 letters)
- python-Levenshtein uses C extension for speed

### 8.3 Caching (Future)

- **LRU cache** for medicine name → ID mappings
- **Redis** for session data
- **Invalidate** on updates

## 9. Testing Philosophy

### 9.1 Test Pyramid

- **70% Unit Tests**: Parsers, utils, database queries
- **20% Integration Tests**: Database + handlers
- **10% E2E Tests**: Full bot flows

### 9.2 Coverage Goals

- **Minimum 85%** overall
- **100%** for critical paths (add, use, search)
- **95%+** for parsers

### 9.3 Test Database

- **In-memory SQLite** for speed
- **Fixtures** for common test data
- **Async tests** with pytest-asyncio

## 10. Monitoring & Observability (Future)

### 10.1 Metrics

- Messages processed per minute
- Parser success rate
- Fuzzy match confidence distribution
- Database query latency

### 10.2 Tools

- **Prometheus + Grafana**: Metrics and dashboards
- **Sentry**: Error tracking and alerting
- **Loguru**: Structured logging with JSON

## 11. Deployment Options

### 11.1 Docker (Recommended)

**Pros:**
- Consistent environment
- Easy updates (rebuild image)
- Resource limits
- Health checks

**Cons:**
- Requires Docker knowledge
- Slight overhead

### 11.2 systemd

**Pros:**
- Native Linux integration
- Automatic restart
- Journal logging

**Cons:**
- Manual dependency management
- Server-specific configuration

### 11.3 Cloud Platforms

**Options:**
- Railway: Zero-config, auto-deploy
- Render: Similar to Railway
- Fly.io: Global edge deployment
- DigitalOcean App Platform

**Considerations:**
- Cold starts on free tiers
- Database persistence (use volumes)
- Cost at scale

## 12. Contributing Guidelines

### 12.1 Code Style

- **PEP 8**: Enforced by black and ruff
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for modules and classes

### 12.2 Pull Request Process

1. Create feature branch
2. Write tests (85%+ coverage)
3. Run code quality checks
4. Update documentation
5. Submit PR with clear description

### 12.3 Code Review Checklist

- [ ] Tests pass
- [ ] Code formatted (black)
- [ ] Linting clean (ruff)
- [ ] Type checking passes (mypy)
- [ ] Documentation updated
- [ ] No sensitive data committed

---

## Summary

The Medi-Cabinet Bot demonstrates:
- **Clean Architecture**: Layered design with clear separation of concerns (Bot → Commands → Services → Repositories)
- **Practical Problem-Solving**: Solves real-world medicine waste issue for Bangladeshi families
- **Pluggable LLM Integration**: Factory pattern with registry for multiple providers
- **Multi-Tier NLU**: Regex (free/fast) + LLM fallback (when configured)
- **Smart Features**: Drug interactions, routine scheduling, cost tracking, analytics
- **Production-Ready**: 170 tests, Alembic migrations, Docker deployment, structured logging
- **User-Centric**: Natural language interface, photo recognition, inline keyboards

This architecture balances simplicity (for maintainability) with sophistication (for real-world use), making it both a strong portfolio project and a practical family tool.
