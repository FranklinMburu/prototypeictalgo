# ICT Trading System - Project Structure Guide

**For Senior Engineers: Complete System Architecture & Organization**

---

## 📁 Root Directory Organization

```
prototypeictalgo/
├── 📘 DOCUMENTATION & ONBOARDING
│   ├── README.md                    # Start here - project overview
│   ├── docs/                        # Comprehensive documentation (100+ guides)
│   │   ├── INDEX.md                 # Documentation navigation index
│   │   ├── system-architecture/     # System design documents
│   │   ├── implementation-guides/   # Integration & feature guides
│   │   ├── quick-references/        # One-page reference guides
│   │   ├── audits-reports/          # Compliance & validation
│   │   ├── api-documentation/       # API specs & webhooks
│   │   ├── setup-guides/            # Installation & deployment
│   │   └── reference/               # Detailed technical specs
│
├── 🚀 CORE APPLICATION CODE
│   ├── ict_trading_system/          # Main trading system (FastAPI)
│   │   ├── src/                     # Source code
│   │   │   ├── services/            # Business logic
│   │   │   ├── utils/               # Utilities & helpers
│   │   │   ├── models/              # Database models
│   │   │   └── __init__.py
│   │   ├── backend/                 # Backend utilities
│   │   ├── pine_script/             # TradingView Pine Script indicators
│   │   └── README.md
│
│   ├── reasoner_service/            # AI Reasoning Engine (Async)
│   │   ├── src/                     # Core reasoning logic
│   │   ├── outcome_*.py             # Outcome evaluation & policies
│   │   ├── alerts.py                # Alert/notification formatting
│   │   └── orchestrator.py          # Orchestration logic
│
│   ├── execution_boundary/          # Execution Boundary Services
│   │   ├── src/                     # Boundary enforcement code
│   │   └── README.md
│
├── 🧪 TESTING & QUALITY ASSURANCE
│   ├── tests/                       # Test suites
│   │   ├── integration/             # End-to-end tests
│   │   └── test_*.py                # Unit & feature tests
│   ├── scripts/testing/             # Test utilities & runners
│   │   ├── run_e2e_test.sh          # End-to-end test runner
│   │   └── run_full_test.sh         # Full test suite
│   ├── pytest.ini                   # Pytest configuration
│   ├── conftest.py                  # Pytest fixtures
│   └── requirements-ci.txt          # CI/CD dependencies
│
├── ⚙️ CONFIGURATION & DEPLOYMENT
│   ├── config/                      # Configuration files
│   │   ├── .env.example             # Environment variables template
│   │   ├── docker-compose.yml       # Docker composition
│   │   ├── Dockerfile               # Container image
│   │   ├── alembic.ini              # Database migration config
│   │   ├── logging.conf.example     # Logging configuration
│   │   ├── prometheus.yml           # Monitoring config
│   │   ├── grafana-dashboard.json   # Dashboard config
│   │   ├── alert.rules.yml          # Alert rules
│   │   ├── ict_trading_system.service.example # Systemd service
│   │   └── pyproject.toml           # Project metadata & dependencies
│
│   ├── scripts/deployment/          # Deployment utilities
│   │   ├── tag_release.sh           # Release tagging
│   │   └── ...
│
│   ├── scripts/utilities/           # General utilities
│   │   ├── runner.py                # Application runner
│   │   └── ...
│
├── 📊 DATA & SAMPLES
│   ├── data/                        # Data files
│   │   ├── samples/                 # Sample payloads & demos
│   │   │   ├── test_payload.json
│   │   │   ├── sample_alert.json
│   │   │   ├── test_signal*.json    # Various test signals
│   │   │   ├── demo.py              # Demo scripts
│   │   │   ├── plan_walkthrough.py
│   │   │   └── ICT_Trading_System_Webhook_Test.postman_collection.json
│   │   └── databases/               # Database files (local only)
│   │       ├── trading_system.db
│   │       └── decisions.db
│
├── 🛠️ TOOLS & UTILITIES
│   ├── tools/                       # Development tools
│   │   ├── release/                 # Release management
│   │   │   └── tag_release.py
│   │   └── monitoring/              # Monitoring utilities
│
│   ├── utils/                       # Shared utilities
│   ├── apps/                        # Additional applications
│   ├── openai_mock/                 # Mock OpenAI service (testing)
│
├── 📝 PROJECT FILES
│   ├── requirements.txt              # Python dependencies
│   ├── .gitignore                   # Git ignore rules
│   ├── .env                         # Environment variables (local, not committed)
│   ├── .git/                        # Git repository
│   └── venv/                        # Python virtual environment
│
└── 📂 SUPPORT DIRECTORIES
    ├── logs/                        # Application logs (runtime)
    ├── examples/                    # Example implementations
    └── ops/                         # Operations & DevOps

```

---

## 🎯 Key Directories Explained

### **1. ict_trading_system/** - Main Trading System
The core FastAPI application that:
- Receives webhook signals from TradingView (Pine Script)
- Validates signals against market structure (ICT concepts)
- Scores confidence levels
- Invokes AI reasoning engine
- Sends alerts via Telegram
- Persists decisions to database

**Structure:**
```
ict_trading_system/
├── src/
│   ├── services/          # Core business logic
│   │   ├── signal_processor.py    # Signal validation & killzone checks
│   │   ├── gemini_adapter.py      # Gemini API integration
│   │   └── telegram_service.py    # Telegram notifications
│   ├── utils/
│   │   ├── memory_agent.py        # Embeddings & memory (ChromaDB)
│   │   └── ...
│   └── models/
│       └── database.py            # SQLAlchemy database models
├── backend/               # Backend utilities
├── pine_script/          # TradingView indicators
└── README.md
```

### **2. reasoner_service/** - AI Reasoning Engine
Async service that:
- Analyzes trading signals using Gemini API
- Evaluates outcome statistics
- Applies policy rules & governance
- Tracks decision outcomes for feedback loops
- Generates human-readable analysis

**Structure:**
```
reasoner_service/
├── orchestrator.py              # Main orchestration logic
├── outcome_stats.py             # Statistics calculation
├── outcome_policy_evaluator.py  # Policy enforcement
├── alerts.py                    # Alert formatting
└── ...service.py                # Various service modules
```

### **3. execution_boundary/** - Execution Guardrails
Safety boundaries that:
- Enforce execution policies
- Validate risk parameters
- Prevent invalid trades
- Log all decisions for audit trails
- Integrate with human approval workflows

### **4. tests/** - Comprehensive Test Suite
```
tests/
├── integration/                 # End-to-end system tests
├── test_signal_processor.py     # Unit tests
├── test_memory_agent.py
└── ...
```

### **5. docs/** - Documentation
100+ organized markdown files:
- System architecture
- Implementation guides
- API documentation
- Quick references
- Audit reports
- See `docs/INDEX.md` for navigation

### **6. config/** - Configuration & Deployment
All configuration files for:
- Environment variables (.env files)
- Docker deployment (Dockerfile, docker-compose.yml)
- Monitoring (Prometheus, Grafana, alerts)
- Database migrations (Alembic)
- Application logging

### **7. data/samples/** - Test Data & Examples
- Test signal payloads (JSON)
- Demo scripts
- Postman collection for webhook testing
- Sample alerts

---

## 🚀 Getting Started - Path for Senior Engineer

### **Phase 1: Understand the System (30 min)**
1. Read: [docs/INDEX.md](docs/INDEX.md)
2. Read: [docs/setup-guides/README.md](docs/setup-guides/README.md)
3. Review: [docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md](docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md)

### **Phase 2: Setup & Run (20 min)**
```bash
# 1. Setup Python environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp config/.env.example .env
# Edit .env with your API keys (GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, etc.)

# 4. Initialize database
python -m scripts.utilities.runner init-db

# 5. Start the system
python -m scripts.utilities.runner start
```

### **Phase 3: Test the System (15 min)**
```bash
# Send a test webhook signal
python data/samples/demo.py

# Or use the Postman collection:
# import: data/samples/ICT_Trading_System_Webhook_Test.postman_collection.json
```

### **Phase 4: Deep Dive (varies)**
- Review specific service code in [ict_trading_system/src/](ict_trading_system/src/)
- Check implementation guides in [docs/implementation-guides/](docs/implementation-guides/)
- Run tests: `pytest tests/`
- Review decision outcomes in database

---

## 📊 Architecture Overview

### **Signal Flow:**
```
TradingView Signal (Webhook)
    ↓
[ict_trading_system] Signal Processor
    ├─ Validate signal format
    ├─ Check killzone (London/NY sessions)
    ├─ Calculate confluence score
    └─ Queue for AI analysis
    ↓
[reasoner_service] AI Analyzer
    ├─ Gemini API analysis
    ├─ Outcome evaluation
    ├─ Policy checking
    └─ Generate explanation
    ↓
[execution_boundary] Enforcement
    ├─ Validate execution risk
    ├─ Apply governance rules
    ├─ Log decision
    └─ Send Telegram alert
    ↓
Database: Store decision + outcome
```

### **Key Technologies:**
- **API Server:** FastAPI + Uvicorn (async)
- **AI/LLM:** Gemini 2.5-flash API
- **Embeddings:** Gemini embedding-004 + ChromaDB
- **Database:** SQLAlchemy + SQLite (local)
- **Async Queue:** Signal queue + background worker
- **Monitoring:** Prometheus + Grafana
- **Notifications:** Telegram Bot API
- **Testing:** pytest + async fixtures

---

## 🔑 Critical Files to Know

| File | Purpose | Edit Frequency |
|------|---------|-----------------|
| [.env](/.env) | API keys, secrets, settings | On setup only |
| [config/pyproject.toml](config/pyproject.toml) | Dependencies, metadata | When adding packages |
| [ict_trading_system/src/services/signal_processor.py](ict_trading_system/src/services/signal_processor.py) | Signal validation logic | Feature development |
| [ict_trading_system/src/utils/memory_agent.py](ict_trading_system/src/utils/memory_agent.py) | Embeddings & memory | AI integration |
| [reasoner_service/orchestrator.py](reasoner_service/orchestrator.py) | AI reasoning flow | Core logic updates |
| [reasoner_service/outcome_policy_evaluator.py](reasoner_service/outcome_policy_evaluator.py) | Policy enforcement | Rules updates |
| [tests/integration/test_end_to_end_system.py](tests/integration/test_end_to_end_system.py) | System validation | Testing improvements |

---

## 🔄 Development Workflow

### **1. Making Changes**
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes to code
# Run tests
pytest tests/

# Run end-to-end test
bash scripts/testing/run_e2e_test.sh

# Commit changes
git commit -m "feat: description of changes"
git push origin feature/your-feature-name
```

### **2. Environment Variables**
```bash
# Required for operation:
GEMINI_API_KEY=your_key           # AI reasoning
TELEGRAM_BOT_TOKEN=your_token     # Notifications
TELEGRAM_CHAT_ID=your_id          # Alert destination
WEBHOOK_SECRET=your_secret        # Webhook validation
OPENAI_API_KEY=optional           # Fallback embedding
EMBEDDING_PROVIDER=gemini         # Which provider to use
```

### **3. Database**
```bash
# SQLite database automatically created on first run
# File: data/databases/trading_system.db

# To reset database:
rm data/databases/trading_system.db
python -m scripts.utilities.runner init-db
```

---

## 📋 Project Dependencies

**Core:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `pydantic` - Validation
- `chromadb` - Vector embeddings
- `requests` - HTTP client

**AI/LLM:**
- `google-generativeai` - Gemini API
- `openai` - OpenAI API (optional)

**Operations:**
- `pytest` - Testing
- `prometheus-client` - Metrics
- `python-dotenv` - Environment loading

See [requirements.txt](requirements.txt) for full list.

---

## 🎓 Learning Resources

For understanding this system:

1. **New to ICT Trading Concepts?**
   - Read: [docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md](docs/system-architecture/COMPLETE_ECOSYSTEM_STATUS.md)
   - Explains: Killzones, Order Blocks, Break of Structure

2. **Need API Integration Details?**
   - Read: [docs/api-documentation/API.md](docs/api-documentation/API.md)
   - Explains: Webhook contracts, payloads, responses

3. **Want to Modify AI Reasoning?**
   - Read: [docs/implementation-guides/PLAN_EXECUTOR_IMPLEMENTATION_COMPLETE.md](docs/implementation-guides/PLAN_EXECUTOR_IMPLEMENTATION_COMPLETE.md)
   - Explains: Decision flow, reasoning engine, policy evaluation

4. **Need to Understand Execution Safety?**
   - Read: [docs/system-architecture/EXECUTION_BOUNDARY_ARCHITECTURE.md](docs/system-architecture/EXECUTION_BOUNDARY_ARCHITECTURE.md)
   - Explains: Risk guardrails, policy enforcement

---

## ✅ Code Quality

- **No debug print statements** - Uses logging module exclusively
- **Type hints** - Python type hints throughout
- **Async-first** - Async/await for I/O operations
- **Error handling** - Exponential backoff & retries built-in
- **Logging** - Structured logging with levels (debug, info, warning, error)
- **Tests** - Integration tests for signal flow validation

---

## 🔒 Security Notes

- **API Keys:** Never commit `.env` file - use environment variables only
- **Database:** SQLite for development; use PostgreSQL in production
- **Webhook Secret:** Validate all incoming signals
- **Telegram Token:** Keep secure, never expose in logs
- **Logging:** No sensitive data in logs (fixed in cleanup)

---

## 📞 Support & Questions

For specific questions about:
- **System Architecture** → See [docs/system-architecture/](docs/system-architecture/)
- **Implementation Details** → See [docs/implementation-guides/](docs/implementation-guides/)
- **Quick Lookup** → See [docs/quick-references/](docs/quick-references/)
- **API Integration** → See [docs/api-documentation/](docs/api-documentation/)
- **Compliance/Audits** → See [docs/audits-reports/](docs/audits-reports/)

---

**Last Updated:** February 8, 2026  
**Version:** 1.0  
**Status:** Production-Ready
