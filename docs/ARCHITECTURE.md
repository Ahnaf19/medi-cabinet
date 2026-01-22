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
│  - Job scheduling (expiry checks, backups)           │
│  - Error handling                                    │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│         Command Layer (commands.py)                   │
│  - Route commands to handlers                        │
│  - Orchestrate business logic                        │
│  - Format responses                                  │
└──────┬────────────┬──────────────┬──────────────────┘
       │            │              │
       ▼            ▼              ▼
┌──────────┐  ┌──────────┐  ┌────────────┐
│ Parsers  │  │ Database │  │  Utilities │
│  (NLP)   │  │  (Repo)  │  │ (Formatters)│
└──────────┘  └──────────┘  └────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│               SQLite Database                         │
│  - medicines table                                   │
│  - activity_log table                                │
└─────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

**Bot Layer** (`src/bot.py`)
- Initialize Telegram application
- Register command and message handlers
- Setup scheduled jobs (expiry checks at 9 AM, backups at 3 AM)
- Configure logging with loguru
- Graceful startup and shutdown

**Command Layer** (`src/commands.py`)
- Handle user commands (`/start`, `/help`, `/delete`, `/stats`)
- Process natural text messages
- Coordinate between parsers and database
- Generate user-friendly responses with emojis and formatting
- Admin authorization checks

**Parser Layer** (`src/parsers.py`)
- Natural language understanding with regex patterns
- Command type detection (add, use, search, list)
- Extract structured data (medicine name, quantity, unit, expiry, location)
- Confidence scoring for ambiguous matches

**Database Layer** (`src/database.py`)
- Repository pattern for clean data access
- Medicine CRUD operations
- Activity logging
- Fuzzy name matching with fuzzywuzzy
- Multi-group isolation (critical for privacy)
- Transaction support for atomic operations

**Utility Layer** (`src/utils.py`)
- Formatting functions (lists, dates, statistics)
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

1. **Regex First** (Fast, Deterministic)
   - Priority-ordered patterns for each command type
   - Handle common variations (`+Napa 10`, `Bought Napa 10`)

2. **Fuzzy Matching** (Typo Tolerance)
   - Levenshtein distance with python-Levenshtein (C extension)
   - Confidence scoring (0-100)
   - Pre-filter by first letter for performance

3. **Future: LLM Fallback**
   - Claude API for complex natural language
   - Structured extraction with MCP tools

**Why Not LLM-Only?**
- Regex is instant and deterministic
- No API costs for simple commands
- LLM can be added as enhancement, not replacement

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
- **Future ML**: Training data for predictive features

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

## 5. Future LLM Integration Plan

### 5.1 MCP Integration

```python
from mcp import Tool, Server

@Tool
async def extract_medicine_info(text: str, image: bytes = None) -> MedicineData:
    """Use Claude API with vision for prescription photos."""
    response = await claude_api.messages.create(
        model="claude-opus-4-5",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image", "source": {"type": "base64", "data": image}}
            ]
        }],
        tools=[medicine_extraction_tool],
    )
    return response.tool_use.input
```

### 5.2 RAG Pipeline for Drug Interactions

```
User Query → Embed Query → Vector Search (ChromaDB)
                                    ↓
                          Retrieve Drug Info
                                    ↓
                         Context + Query → Claude
                                    ↓
                            Interaction Warning
```

**Data Sources:**
- FDA drug interaction database
- WHO essential medicines list
- Bangladesh-specific medicine data

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
- **Clean Architecture**: Layered design with clear separation of concerns
- **Practical Problem-Solving**: Solves real-world medicine waste issue
- **Extensibility**: Ready for Phase 2 LLM integration
- **Production-Ready**: Error handling, logging, testing, deployment
- **User-Centric**: Natural language interface, zero friction

This architecture balances simplicity (for maintainability) with sophistication (for future enhancements), making it an excellent portfolio project and practical family tool.
