# 💊 Medi-Cabinet Bot

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production-success)

> **A Telegram bot helping Bangladeshi families reduce medicine waste through smart inventory tracking**

## 📊 The Problem

In Bangladesh and many developing countries, medicine waste is a significant issue:
- Families buy medicines in bulk but forget about leftover stock
- Medicines expire unused, leading to financial loss
- Lack of simple tracking causes duplicate purchases
- Multi-generational households struggle with paper-based tracking

**Medi-Cabinet Bot** solves this by providing a zero-friction, natural language interface for families to track their medicine inventory right in their Telegram group chats.

## 🏗️ Architecture

### Phase 1: Current (MVP)

```mermaid
graph LR
    A[👥 Family Group Chat] --> B[🤖 Telegram Bot]
    B --> C[📝 Natural Language Parser]
    C --> D[⚙️ Command Handlers]
    D --> E[🗄️ SQLite Database]
    E --> F[(Medicines<br/>Activity Log)]
    D --> G[📊 Analytics & Alerts]
```

**Key Components:**
- **Natural Language Parser**: Understands commands like "Got Napa 10" or "Used 2 Napa"
- **Fuzzy Matching**: Handles typos and name variations (e.g., "Nappa" → "Napa")
- **Multi-Group Support**: Each family group has isolated data
- **Activity Logging**: Complete audit trail of all actions

### Phase 2: Future (LLM-Enhanced)

```mermaid
graph LR
    A[👥 Telegram] --> B[🤖 Bot]
    B --> C{🧠 LLM Router}
    C --> D[Claude API]
    D --> E[🔧 MCP Tools]
    E --> F[🔍 Vector DB<br/>ChromaDB]
    E --> G[🗄️ SQLite]
    E --> H[📷 OCR/Vision]
    E --> I[💊 Drug Interactions<br/>RAG]
```

**Planned Enhancements:**
- **LLM Integration**: Claude API for advanced natural language understanding
- **Image Processing**: OCR for reading prescriptions and medicine packets
- **Drug Interactions**: RAG-based warnings for medicine interactions
- **Routine Reminders**: Track medicine schedules with alarms

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- Python 3.10 or higher
- Telegram account
- 5 minutes of your time

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ahnaftanjid/medi-cabinet.git
   cd medi-cabinet
   ```

2. **Install uv** (fast Python package installer)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Create your Telegram bot**
   - Open Telegram and search for [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow instructions
   - Copy your bot token

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and paste your bot token
   ```

5. **Install dependencies and run**
   ```bash
   uv sync
   alembic upgrade head  # Initialize database
   uv run python run.py
   ```

6. **Start using the bot!**
   - Add your bot to a Telegram group
   - Send `/start` to see the welcome message
   - Start tracking: `+Napa 10`

## 📱 Usage Examples

### Adding Medicines

```
You: +Napa 10
Bot: ✅ Added Napa (10 tablets)
     📍 Total now: 10 tablets
```

```
You: Bought Napa Extra 20 tablets, expires Dec 2025
Bot: ✅ Added Napa Extra (20 tablets)
     ⚠️ Expiring in 300 days
```

### Using Medicines

```
You: -Napa 2
Bot: ✅ Used 2 tablets of Napa
     📍 Remaining: 8 tablets
```

```
You: Took some paracetamol
Bot: ✅ Used 1 tablet of Paracetamol
     📍 Remaining: 11 tablets
     ⚠️ Low stock! Only 2 left.
```

### Searching

```
You: ?Napa
Bot: 💊 Found: Napa
     Quantity: 8 tablets
     Added by: Ahnaf
     Added on: Today
```

```
You: Do we have Sergel?
Bot: 💊 Found: Sergel
     Quantity: 5 tablets
     Expiry: Expires Dec 2026
     Location: Bedroom Drawer
```

### Listing All Medicines

```
You: ?all
Bot: 💊 Medicine Cabinet (Total: 3)

     💊 Napa - 8 tablets
     💊 Napa Extra - 20 tablets (Expires Dec 2025)
     ⚠️ Sergel - 2 tablets

     ⚠️ Low Stock Alert!
     ⚠️ Sergel - Only 2 tablets left!
```

## 🎯 Command Reference

| Command | Example | Description |
|---------|---------|-------------|
| **Add Medicine** | `+Napa 10` | Add medicine to inventory |
| | `Bought Napa Extra 10 tablets` | Natural language add |
| | `Got paracetamol, 12, expires Dec 2025` | With expiry date |
| **Use Medicine** | `-Napa 2` | Use/consume medicine |
| | `Used 2 Napa` | Natural language use |
| | `Took some paracetamol` | "some" defaults to 1 |
| **Search** | `?Napa` | Search for specific medicine |
| | `Do we have Napa?` | Natural question |
| | `Check sergel` | Alternative search |
| **List All** | `?all` | List all medicines |
| | `list medicines` | Alternative list |
| | `inventory` | Show inventory |
| **Delete** | `/delete Napa` | Delete medicine (admin only) |
| **Statistics** | `/stats` | Show usage statistics |
| **Help** | `/help` | Show detailed help |

## 🛠️ Development

### Project Structure

```
medi-cabinet/
├── src/
│   ├── bot.py              # Main bot application
│   ├── commands.py         # Command handlers
│   ├── parsers.py          # Natural language parsing
│   ├── database.py         # Database operations (repository pattern)
│   └── utils.py            # Helper functions
├── config/
│   └── config.py           # Configuration management (Pydantic)
├── migrations/
│   ├── env.py              # Alembic environment
│   └── versions/           # Database migrations
├── tests/
│   ├── conftest.py         # Pytest fixtures
│   ├── test_parsers.py     # Parser tests
│   └── test_database.py    # Database tests
├── docs/
│   └── ARCHITECTURE.md     # Detailed architecture documentation
├── .env.example            # Environment variable template
├── pyproject.toml          # Project dependencies and config
├── alembic.ini             # Database migration config
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker orchestration
└── run.py                  # Entry point
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_parsers.py -v
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type check
uv run mypy src/
```

## 🚢 Deployment

### Docker (Recommended)

1. **Build and run**
   ```bash
   docker-compose up -d
   ```

2. **Check logs**
   ```bash
   docker-compose logs -f bot
   ```

3. **Stop**
   ```bash
   docker-compose down
   ```

### Manual Deployment

1. **On a VPS (DigitalOcean, Linode, etc.)**
   ```bash
   # Clone repository
   git clone https://github.com/ahnaftanjid/medi-cabinet.git
   cd medi-cabinet

   # Install dependencies
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv sync

   # Configure
   cp .env.example .env
   # Edit .env with your bot token

   # Initialize database
   alembic upgrade head

   # Run with screen or tmux
   screen -S medi-bot
   uv run python run.py
   ```

2. **Using systemd (Linux)**
   Create `/etc/systemd/system/medi-cabinet.service`:
   ```ini
   [Unit]
   Description=Medi-Cabinet Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=your_user
   WorkingDirectory=/path/to/medi-cabinet
   ExecStart=/path/to/uv run python run.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable medi-cabinet
   sudo systemctl start medi-cabinet
   ```

## ⚙️ Configuration

Edit `.env` file:

```bash
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Database Configuration
DATABASE_PATH=medi-cabinet.db

# Logging Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Admin User IDs (comma-separated, get from @userinfobot)
ADMIN_USER_IDS=123456789,987654321

# Medicine Tracking Settings
LOW_STOCK_THRESHOLD=3              # Alert when quantity < this
EXPIRY_WARNING_DAYS=30             # Warn when expiring within N days
FUZZY_MATCH_THRESHOLD=80           # Fuzzy matching sensitivity (0-100)
```

## 🗺️ Roadmap

- [x] **Phase 1: Text-Based Tracking (Current)**
  - [x] Natural language command parsing
  - [x] Fuzzy medicine name matching
  - [x] Multi-group support with data isolation
  - [x] Activity logging and statistics
  - [x] Low stock and expiry alerts
  - [x] Docker deployment

- [ ] **Phase 2: LLM Integration**
  - [ ] Claude API for advanced NLU
  - [ ] MCP (Model Context Protocol) for tool calling
  - [ ] Structured data extraction

- [ ] **Phase 3: Image Processing**
  - [ ] OCR for prescription reading
  - [ ] Vision LLM for medicine packet recognition
  - [ ] Automatic expiry date extraction from photos

- [ ] **Phase 4: Smart Features**
  - [ ] Medicine interaction warnings (RAG-based)
  - [ ] Vector database for similarity search (ChromaDB)
  - [ ] Routine tracking with alarms
  - [ ] Before/after meal reminders

- [ ] **Phase 5: Analytics & Insights**
  - [ ] Usage patterns analysis
  - [ ] Predictive inventory alerts
  - [ ] Cost tracking and savings calculator

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add type hints to all functions
- Write tests for new features
- Update documentation
- Run code quality checks before submitting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Database migrations with [Alembic](https://alembic.sqlalchemy.org/)
- Configuration with [Pydantic](https://docs.pydantic.dev/)
- Logging with [Loguru](https://github.com/Delgan/loguru)
- Package management with [uv](https://github.com/astral-sh/uv)

## 📞 Support

If you encounter any issues or have questions:
- Open an issue on [GitHub](https://github.com/ahnaftanjid/medi-cabinet/issues)
- Check the [ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details

---

**Made with ❤️ for Bangladeshi families | Portfolio project demonstrating clean architecture and practical problem-solving**
