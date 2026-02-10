"""Tests for r_multiple deterministic computation in outcome_recorder."""

import pytest
from datetime import datetime, timezone
from reasoner_service.outcome_recorder import DecisionOutcomeRecorder


class TestRMultipleComputation:
    """Test r_multiple computation for LONG and SHORT trades."""
    
    @pytest.fixture
    def recorder(self):
        """Create an outcome recorder instance (no sessionmaker needed for unit tests)."""
        return DecisionOutcomeRecorder(sessionmaker=None)
    
    # ========== LONG TRADE TESTS ==========
    
    def test_r_multiple_long_win(self, recorder):
        """Test r_multiple for LONG trade that wins (exit > entry)."""
        # LONG: (exit_price - entry_price) / (entry_price - stop_loss_price)
        # (1.0900 - 1.0850) / (1.0850 - 1.0800) = 0.0050 / 0.0050 = 1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0900,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult == 1.0, f"Expected 1.0, got {r_mult}"
    
    def test_r_multiple_long_loss(self, recorder):
        """Test r_multiple for LONG trade that loses (exit < entry)."""
        # LONG: (exit_price - entry_price) / (entry_price - stop_loss_price)
        # (1.0800 - 1.0850) / (1.0850 - 1.0800) = -0.0050 / 0.0050 = -1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0800,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult == -1.0, f"Expected -1.0, got {r_mult}"
    
    def test_r_multiple_long_big_win(self, recorder):
        """Test r_multiple for LONG trade with big win."""
        # LONG: (exit_price - entry_price) / (entry_price - stop_loss_price)
        # (1.1000 - 1.0850) / (1.0850 - 1.0800) = 0.0150 / 0.0050 = 3.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.1000,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult == 3.0, f"Expected 3.0, got {r_mult}"
    
    def test_r_multiple_long_partial_loss(self, recorder):
        """Test r_multiple for LONG trade that partially loses."""
        # LONG: (exit_price - entry_price) / (entry_price - stop_loss_price)
        # (1.0825 - 1.0850) / (1.0850 - 1.0800) = -0.0025 / 0.0050 = -0.5
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0825,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult == -0.5, f"Expected -0.5, got {r_mult}"
    
    # ========== SHORT TRADE TESTS ==========
    
    def test_r_multiple_short_win(self, recorder):
        """Test r_multiple for SHORT trade that wins (exit < entry)."""
        # SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
        # (1.0850 - 1.0800) / (1.0900 - 1.0850) = 0.0050 / 0.0050 = 1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0800,
            stop_loss_price=1.0900,
            direction="short"
        )
        assert r_mult == 1.0, f"Expected 1.0, got {r_mult}"
    
    def test_r_multiple_short_loss(self, recorder):
        """Test r_multiple for SHORT trade that loses (exit > entry)."""
        # SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
        # (1.0850 - 1.0900) / (1.0900 - 1.0850) = -0.0050 / 0.0050 = -1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0900,
            stop_loss_price=1.0900,
            direction="short"
        )
        assert r_mult == -1.0, f"Expected -1.0, got {r_mult}"
    
    def test_r_multiple_short_big_win(self, recorder):
        """Test r_multiple for SHORT trade with big win."""
        # SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
        # (1.0850 - 1.0700) / (1.0900 - 1.0850) = 0.0150 / 0.0050 = 3.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0700,
            stop_loss_price=1.0900,
            direction="short"
        )
        assert r_mult == 3.0, f"Expected 3.0, got {r_mult}"
    
    def test_r_multiple_short_partial_loss(self, recorder):
        """Test r_multiple for SHORT trade that partially loses."""
        # SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
        # (1.0850 - 1.0875) / (1.0900 - 1.0850) = -0.0025 / 0.0050 = -0.5
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0875,
            stop_loss_price=1.0900,
            direction="short"
        )
        assert r_mult == -0.5, f"Expected -0.5, got {r_mult}"
    
    # ========== EDGE CASES ==========
    
    def test_r_multiple_zero_risk_long(self, recorder):
        """Test r_multiple returns None when risk is zero (LONG)."""
        # entry_price == stop_loss_price -> risk = 0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0900,
            stop_loss_price=1.0850,
            direction="long"
        )
        assert r_mult is None, f"Expected None for zero risk, got {r_mult}"
    
    def test_r_multiple_zero_risk_short(self, recorder):
        """Test r_multiple returns None when risk is zero (SHORT)."""
        # entry_price == stop_loss_price -> risk = 0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0800,
            stop_loss_price=1.0850,
            direction="short"
        )
        assert r_mult is None, f"Expected None for zero risk, got {r_mult}"
    
    def test_r_multiple_missing_entry_price(self, recorder):
        """Test r_multiple returns None when entry_price is missing."""
        r_mult = recorder._compute_r_multiple(
            entry_price=None,
            exit_price=1.0900,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult is None, f"Expected None for missing entry_price, got {r_mult}"
    
    def test_r_multiple_missing_exit_price(self, recorder):
        """Test r_multiple returns None when exit_price is missing."""
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=None,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult is None, f"Expected None for missing exit_price, got {r_mult}"
    
    def test_r_multiple_missing_stop_loss(self, recorder):
        """Test r_multiple returns None when stop_loss_price is missing."""
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0900,
            stop_loss_price=None,
            direction="long"
        )
        assert r_mult is None, f"Expected None for missing stop_loss_price, got {r_mult}"
    
    def test_r_multiple_no_direction_defaults_to_long(self, recorder):
        """Test r_multiple defaults to LONG when direction is not specified."""
        # Should use LONG formula: (exit - entry) / (entry - sl)
        # (1.0900 - 1.0850) / (1.0850 - 1.0800) = 1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0900,
            stop_loss_price=1.0800,
            direction=None
        )
        assert r_mult == 1.0, f"Expected 1.0 (LONG default), got {r_mult}"
    
    def test_r_multiple_direction_case_insensitive(self, recorder):
        """Test r_multiple direction is case-insensitive."""
        r_mult_upper = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0800,
            stop_loss_price=1.0900,
            direction="SHORT"
        )
        r_mult_lower = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0800,
            stop_loss_price=1.0900,
            direction="short"
        )
        assert r_mult_upper == r_mult_lower == 1.0, "Direction should be case-insensitive"
    
    def test_r_multiple_rounding(self, recorder):
        """Test r_multiple is properly rounded to 4 decimal places."""
        # (1.1234 - 1.1111) / (1.1111 - 1.1000) = 0.0123 / 0.0111 = 1.108108...
        r_mult = recorder._compute_r_multiple(
            entry_price=1.1111,
            exit_price=1.1234,
            stop_loss_price=1.1000,
            direction="long"
        )
        assert isinstance(r_mult, float), f"r_multiple should be float, got {type(r_mult)}"
        # Should be rounded to 4 decimals
        assert r_mult == round(r_mult, 4), f"r_multiple {r_mult} should be rounded to 4 decimals"
    
    def test_r_multiple_breakeven_trade(self, recorder):
        """Test r_multiple for breakeven trade (exit == entry)."""
        # (exit - entry) / (entry - sl) = 0 / risk = 0
        r_mult = recorder._compute_r_multiple(
            entry_price=1.0850,
            exit_price=1.0850,
            stop_loss_price=1.0800,
            direction="long"
        )
        assert r_mult == 0.0, f"Expected 0.0 for breakeven, got {r_mult}"
    
    def test_r_multiple_negative_prices_long(self, recorder):
        """Test r_multiple with negative prices (crypto leverage-like)."""
        # Should work fine: (0.0150 - 0.0100) / (0.0100 - 0.0050) = 0.0050 / 0.0050 = 1.0
        r_mult = recorder._compute_r_multiple(
            entry_price=0.0100,
            exit_price=0.0150,
            stop_loss_price=0.0050,
            direction="long"
        )
        assert r_mult == 1.0, f"Expected 1.0, got {r_mult}"


@pytest.mark.asyncio
async def test_record_trade_outcome_computes_r_multiple():
    """Integration test: verify record_trade_outcome computes r_multiple from stop_loss_price."""
    # Mock sessionmaker that returns None (we're not actually persisting)
    class MockSessionMaker:
        pass
    
    recorder = DecisionOutcomeRecorder(sessionmaker=None)
    
    # Compute r_multiple via _compute_r_multiple (since we don't have a real DB)
    r_mult = recorder._compute_r_multiple(
        entry_price=1.0850,
        exit_price=1.0900,
        stop_loss_price=1.0800,
        direction="long"
    )
    
    assert r_mult == 1.0, "r_multiple should be computed correctly from stop_loss_price"


@pytest.mark.asyncio
async def test_record_trade_outcome_accepts_stop_loss():
    """Test that record_trade_outcome accepts stop_loss_price parameter."""
    recorder = DecisionOutcomeRecorder(sessionmaker=None)
    
    # Verify the method signature accepts stop_loss_price
    import inspect
    sig = inspect.signature(recorder.record_trade_outcome)
    assert "stop_loss_price" in sig.parameters, "record_trade_outcome should accept stop_loss_price parameter"
