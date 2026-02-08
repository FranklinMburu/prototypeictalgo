# ICT Trading System - Prototype

**A production-ready algorithmic trading system combining ICT Market Structure analysis with AI reasoning, automated signal processing, and execution guardrails.**

> **For new engineers:** Start with [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md), then visit [docs/INDEX.md](docs/INDEX.md)

---

## 🎯 Quick Start

### Prerequisites
- Python 3.9+
- Gemini API key (for AI reasoning)
- TradingView account (for Pine Script signals)
- Telegram bot token (for alerts)

### Setup (5 minutes)

```bash
# 1. Clone and enter directory
cd prototypeictalgo

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp config/.env.example .env
# Edit .env and add your API keys:
# GEMINI_API_KEY=your_key
# TELEGRAM_BOT_TOKEN=your_token
# TELEGRAM_CHAT_ID=your_chat_id
# WEBHOOK_SECRET=your_secret

# 5. Initialize database
python -c "from ict_trading_system.src.models.database import init_db; import asyncio; asyncio.run(init_db())"

# 6. Start the system
python -m uvicorn ict_trading_system.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Test the System

```bash
# Send a test signal
python data/samples/demo.py

# Or use Postman
# Import: data/samples/ICT_Trading_System_Webhook_Test.postman_collection.json
# Hit: POST http://localhost:8000/webhook/signal

# Run tests
pytest tests/integration/test_end_to_end_system.py -v
```

---

## 📚 Documentation

### For Different Roles:

**👨‍💼 Product Manager / Business Stakeholder**
- [docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md](docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md) - System overview
- [docs/audits-reports/](docs/audits-reports/) - Compliance & validation reports

**👨‍💻 Backend Engineer**
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - System architecture guide
- [docs/implementation-guides/](docs/implementation-guides/) - Implementation details
- [ict_trading_system/README.md](ict_trading_system/README.md) - Core system guide

**🤖 AI/LLM Engineer**
- [docs/system-architecture/REASONING_MANAGER_DESIGN.md](docs/system-architecture/REASONING_MANAGER_DESIGN.md) - AI reasoning architecture
- [docs/implementation-guides/PLAN_EXECUTOR_IMPLEMENTATION_COMPLETE.md](docs/implementation-guides/PLAN_EXECUTOR_IMPLEMENTATION_COMPLETE.md) - LLM integration

**🛡️ Security/DevOps Engineer**
- [docs/audits-reports/TECHNICAL_AUDIT_COMPREHENSIVE.md](docs/audits-reports/TECHNICAL_AUDIT_COMPREHENSIVE.md) - Security audit
- [config/](config/) - All configuration templates
- [docs/system-architecture/EXECUTION_BOUNDARY_ARCHITECTURE.md](docs/system-architecture/EXECUTION_BOUNDARY_ARCHITECTURE.md) - Safety guardrails

**📊 QA/Test Engineer**
- [docs/audits-reports/END_TO_END_EXECUTION_REPORT.md](docs/audits-reports/END_TO_END_EXECUTION_REPORT.md) - Test report
- [tests/](tests/) - Test suite
- [scripts/testing/](scripts/testing/) - Test utilities

### All Documentation
See **[docs/INDEX.md](docs/INDEX.md)** for complete navigation guide (100+ documents organized by topic).

---

## 🏗️ System Architecture

### High-Level Flow
```
TradingView Signal
        ↓
    [Signal Processor]
    - Validate format
    - Check killzones
    - Score confluence
        ↓
    [AI Reasoning Engine]
    - Gemini API analysis
    - Outcome evaluation
    - Policy enforcement
        ↓
    [Execution Boundary]
    - Risk validation
    - Safety checks
    - Decision logging
        ↓
    [Notifications & Persistence]
    - Telegram alerts
    - Database storage
    - Audit trail
```

### Key Components

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **ict_trading_system** | Signal processing & validation | FastAPI, SQLAlchemy, AsyncIO |
| **reasoner_service** | AI-powered decision making | Gemini API, ChromaDB, Async |
| **execution_boundary** | Risk management & guardrails | Policy engine, Decision logging |
| **memory_agent** | Embeddings & signal memory | Gemini/OpenAI embeddings, ChromaDB |

---

## 📁 Project Structure

**Clean, organized directory layout:**

```
prototypeictalgo/
├── 📘 docs/                    # 100+ organized documentation
│   ├── INDEX.md               # Start here for docs navigation
│   ├── system-architecture/   # Architecture & design docs
│   ├── implementation-guides/ # Implementation guides
│   ├── quick-references/      # One-page reference guides
│   ├── audits-reports/        # Compliance & validation
│   ├── api-documentation/     # API specs & integration
│   ├── setup-guides/          # Setup & deployment
│   └── reference/             # Detailed technical specs
│
├── 🚀 ict_trading_system/     # Main trading application
│   ├── src/
│   │   ├── services/          # Signal processor, Telegram, Gemini adapter
│   │   ├── utils/             # Memory agent, helpers
│   │   └── models/            # Database models
│   ├── backend/               # Backend utilities
│   ├── pine_script/           # TradingView indicators
│   └── README.md
│
├── 🤖 reasoner_service/       # AI reasoning engine
│   ├── orchestrator.py        # Main reasoning flow
│   ├── outcome_*.py           # Outcome evaluation & policies
│   └── alerts.py              # Alert formatting
│
├── 🛡️ execution_boundary/     # Execution safety guardrails
│   ├── src/                   # Safety enforcement
│   └── README.md
│
├── 🧪 tests/                  # Test suite
│   ├── integration/           # End-to-end system tests
│   └── test_*.py              # Unit tests
│
├── ⚙️ config/                 # Configuration files
│   ├── .env.example           # Environment variables template
│   ├── docker-compose.yml     # Docker setup
│   ├── Dockerfile             # Container image
│   ├── pyproject.toml         # Project metadata
│   └── ...                    # Alembic, logging, monitoring configs
│
├── 📊 data/                   # Data & samples
│   ├── samples/               # Test signals, demo scripts, Postman collection
│   └── databases/             # SQLite databases (not committed)
│
├── 📋 scripts/                # Utility scripts
│   ├── testing/               # Test runners (run_e2e_test.sh)
│   ├── deployment/            # Release management
│   └── utilities/             # General utilities
│
├── 🛠️ tools/                  # Development tools
│   ├── release/               # Release tagging
│   └── monitoring/            # Monitoring utilities
│
├── 📝 Project Files
│   ├── PROJECT_STRUCTURE.md   # Detailed structure guide (for engineers)
│   ├── README.md              # This file
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # Environment variables (not committed)
│   ├── .gitignore             # Git ignore rules
│   ├── pytest.ini             # Test configuration
│   └── conftest.py            # Test fixtures
│
└── 🔧 Support
    ├── venv/                  # Python virtual environment
    ├── logs/                  # Application runtime logs
    ├── .github/               # GitHub workflows
    └── utils/, apps/, ops/    # Additional utilities
```

See **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** for detailed explanations.

---

## 🔌 API Endpoints

### Webhook Endpoint
```
POST /webhook/signal
```
Receives TradingView Pine Script signals with market structure data.

**Example Payload:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "4H",
  "signal_type": "bullish_bos",
  "entry": 1.0950,
  "stop_loss": 1.0900,
  "take_profit": 1.1050,
  "confidence": 85,
  "session": "london",
  "structure": {
    "bos": true,
    "killzone_active": false
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "signal_id": "sig_12345",
  "analysis": {
    "score": 92,
    "explanation": "...",
    "decision": "ALLOW"
  }
}
```

See **[docs/api-documentation/](docs/api-documentation/)** for full API documentation.

---

## 🚀 Deployment

### Docker
```bash
# Build and run with Docker
docker-compose -f config/docker-compose.yml up --build

# Or manually
docker build -f config/Dockerfile -t ict-trading-system .
docker run -p 8000:8000 --env-file .env ict-trading-system
```

### Production Deployment
See **[docs/setup-guides/](docs/setup-guides/)** for detailed deployment guides.

---

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/integration/test_end_to_end_system.py -v

# With coverage
pytest tests/ --cov=ict_trading_system --cov=reasoner_service
```

### Integration Tests
```bash
# Full end-to-end test
bash scripts/testing/run_e2e_test.sh

# Demo signal
python data/samples/demo.py
```

---

## 🔐 Security

### Environment Variables
**Never commit `.env` file.** Use environment variables for:
- `GEMINI_API_KEY` - AI reasoning
- `TELEGRAM_BOT_TOKEN` - Notifications
- `TELEGRAM_CHAT_ID` - Alert destination
- `WEBHOOK_SECRET` - Webhook validation
- `OPENAI_API_KEY` - Optional fallback

### Database
- Development: SQLite (local file)
- Production: PostgreSQL (recommended)

### Code Quality
- ✅ No debug print statements (logging only)
- ✅ Type hints throughout
- ✅ Async-first design
- ✅ Comprehensive error handling
- ✅ Exponential backoff for API calls
- ✅ Complete audit trails

---

## 📊 Monitoring & Observability

### Metrics
- Prometheus-compatible metrics at `/metrics`
- Grafana dashboard configuration included

### Logging
- Structured logging with levels (debug, info, warning, error)
- Application logs in `/logs`
- No sensitive data in logs (API keys, tokens)

### Alerting
- Telegram notifications for signals
- Alert rules in `config/alert.rules.yml`

---

## 🛠️ Development

### Code Organization
```
ict_trading_system/src/
├── services/
│   ├── signal_processor.py     # Signal validation, killzone checks
│   ├── gemini_adapter.py       # Gemini API calls
│   ├── telegram_service.py     # Telegram notifications
│   └── reasoner_factory.py     # Provider selection
├── utils/
│   ├── memory_agent.py         # Embeddings & memory
│   └── helpers.py
└── models/
    └── database.py             # SQLAlchemy models
```

### Making Changes
```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
pytest tests/

# Commit
git commit -m "feat: description"
git push origin feature/your-feature
```

---

## 📖 Key Resources

| Resource | Purpose |
|----------|---------|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Complete architecture guide for engineers |
| [docs/INDEX.md](docs/INDEX.md) | Navigation index for all documentation |
| [docs/system-architecture/](docs/system-architecture/) | System design & architecture |
| [docs/implementation-guides/](docs/implementation-guides/) | Implementation details |
| [docs/quick-references/](docs/quick-references/) | One-page reference guides |
| [ict_trading_system/README.md](ict_trading_system/README.md) | Trading system specifics |
| [tests/integration/](tests/integration/) | E2E test examples |

---

## 🎓 Learning Path

### For New Team Members
1. **Day 1:** Read [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
2. **Day 2:** Review [docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md](docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md)
3. **Day 3:** Setup system locally, run tests
4. **Week 1:** Understand signal flow, review code
5. **Week 2:** Deep dive into specific component
6. **Week 3:** Make first contribution

---

## ❓ FAQ

**Q: How do I add a new trading signal type?**
- A: See [docs/implementation-guides/](docs/implementation-guides/)

**Q: How do I change the AI reasoning logic?**
- A: Edit `reasoner_service/orchestrator.py`, see docs for examples

**Q: How do I integrate with a new broker?**
- A: See [docs/api-documentation/](docs/api-documentation/) for webhook contracts

**Q: What's the testing strategy?**
- A: Integration tests in `tests/integration/`, run with `pytest`

**Q: How do I deploy to production?**
- A: See [docs/setup-guides/](docs/setup-guides/) for deployment guides

---

## 📞 Support

### Documentation
- Full documentation: [docs/INDEX.md](docs/INDEX.md)
- Architecture guide: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- System specifics: [ict_trading_system/README.md](ict_trading_system/README.md)

### Code
- Well-commented source code
- Type hints throughout
- Integration tests as examples

### Questions?
Check relevant documentation folder:
- Architecture? → [docs/system-architecture/](docs/system-architecture/)
- Implementation? → [docs/implementation-guides/](docs/implementation-guides/)
- API? → [docs/api-documentation/](docs/api-documentation/)
- Setup? → [docs/setup-guides/](docs/setup-guides/)
- Audit/Compliance? → [docs/audits-reports/](docs/audits-reports/)

---

## 📊 Status

| Component | Status | Last Updated |
|-----------|--------|--------------|
| Signal Processing | ✅ Production | Feb 8, 2026 |
| AI Reasoning | ✅ Production | Feb 8, 2026 |
| Execution Boundary | ✅ Production | Feb 8, 2026 |
| Testing | ✅ Complete | Feb 8, 2026 |
| Documentation | ✅ 100+ docs | Feb 8, 2026 |
| Code Quality | ✅ Clean | Feb 8, 2026 |
| Deployment | ✅ Ready | Feb 8, 2026 |

---

## 📄 License

[Add your license here]

---

## 👥 Contributing

[Add contribution guidelines here]

---

**Created:** 2024  
**Last Updated:** February 8, 2026  
**Version:** 1.0 - Production Ready  
**Maintainer:** ICT Trading System Team
