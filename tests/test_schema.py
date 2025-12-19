"""Tests for Decision schema validation/coercion."""


# No Decision, Triggers, Versions in current codebase. Import Signal, Analysis, Trade, Setting from the real schemas module.
import pytest
from ict_trading_system.src.models.schemas import Signal, Analysis, Trade, Setting
from pydantic import ValidationError


# No Decision schema in current codebase. Example test for Signal schema:
def test_signal_schema_fields():
    data = {
        "symbol": "BTCUSD",
        "timeframe": "1H",
        "signal_type": "CHoCH",
        "confidence": 95,
        "raw_data": None,
        "timestamp": None
    }
    s = Signal(id=1, **data)
    assert s.symbol == "BTCUSD"
    assert s.confidence == 95


# No drivers field in Signal. Example negative test for missing required field:
def test_signal_missing_required():
    data = {
        "timeframe": "1H",
        "signal_type": "CHoCH",
        "confidence": 95
    }
    with pytest.raises(ValidationError):
        Signal(**data)
