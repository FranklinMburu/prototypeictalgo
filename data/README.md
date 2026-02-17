# Data Directory Policy

## Why Data Is NOT Committed to Git

This `/data` directory is **intentionally excluded from version control** (see `.gitignore`) for the following reasons:

### 1. **Size**
- **TrueFX Raw Ticks** (`data/raw/EURUSD-2026-01.csv`): ~30 MB
- **Processed M1 Candles** (`data/processed/EURUSD/M1/`): ~1.7 MB
- **Signal Exports** (`.jsonl`): Variable, typically 10-100 KB per symbol

Git is not optimized for large binary or data files. Committing these files would bloat the repository history and slow down clone/pull operations.

### 2. **Regenerable**
All data in this directory is **regenerable** from source:
- TrueFX raw ticks: Can be re-downloaded from TrueFX feed
- M1 candles: Can be re-aggregated from raw ticks using `scripts/convert_truefx_ticks_to_m1.py`
- Signal exports: Can be re-generated from database using signal exporters
- Databases: Built from webhook ingestion (real-time data)

### 3. **Local Execution Only**
All data is generated and used **locally during development/testing**. No shared data synchronization is needed across team members or CI/CD pipelines. Each environment generates its own data from source.

### 4. **Security & Privacy**
Market data and trading signals may contain sensitive information (timing, patterns, PnL outcomes). Keeping data local reduces exposure.

---

## Directory Structure

```
data/
├── databases/                  # SQLite databases (also .gitignored)
│   ├── trading_system.db       # 49 real Pine webhook signals
│   ├── decisions.db            # [Planned] Orchestrator decisions
│   └── paper_trading_*.db      # Paper trading experiment results
│
├── raw/                        # Raw market data (NOT committed)
│   ├── truefx/
│   │   └── EURUSD-2026-01.csv  # 755K+ tick data, ~30 MB
│   └── ...
│
└── processed/                  # Processed outputs (NOT committed)
    ├── EURUSD/
    │   ├── M1/
    │   │   └── EURUSD-2026-01-M1.csv  # 30,313 M1 candles
    │   ├── signals.jsonl              # Synthetic signal export (127 lines)
    │   └── real_signals.jsonl         # Real webhook signals (49 lines)
    └── ...
```

---

## How to Regenerate Data

### 1. **M1 Candles from TrueFX Ticks**
```bash
python scripts/convert_truefx_ticks_to_m1.py \
  --input data/raw/truefx/EURUSD-2026-01.csv \
  --output data/processed/EURUSD/M1/EURUSD-2026-01-M1.csv
```

### 2. **Signals from Real Webhook Database**
```bash
python << 'EOF'
import sqlite3, json
conn = sqlite3.connect("data/databases/trading_system.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM signals")
# Export to JSONL...
EOF
```

### 3. **Paper Trading Results**
```bash
python scripts/run_paper_experiment.py  # Writes to data/databases/paper_trading_*.db
```

---

## Development Workflow

1. **Data is LOCAL**: Each developer/environment generates its own copy
2. **Code is SHARED**: All algorithms, scripts, and configurations are committed to git
3. **Results are DOCUMENTED**: Test outputs and metrics are saved in `docs/audits-reports/`

This ensures reproducibility without bloating the repository.

---

## Policy Summary

| Artifact | Committed? | Reason |
|----------|-----------|--------|
| Code (`.py`, `.pine`) | ✅ Yes | Source of truth, must be versioned |
| Configs (`.yaml`, `.env.example`) | ✅ Yes | Setup instructions, must be shared |
| Docs (`.md` in `/docs`) | ✅ Yes | Knowledge & audit trails |
| **Raw market data** | ❌ No | Large, regenerable, not source code |
| **Processed data** | ❌ No | Generated locally, runtime artifacts |
| **Databases** | ❌ No | Local state, not shared across environments |
| **Secrets** (`.env`) | ❌ No | Security risk |

---

**Last Updated:** 2026-02-17  
**Status:** Data exclusion policy documented and enforced
