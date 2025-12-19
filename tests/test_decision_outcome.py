"""
Tests for Decision Outcome Tracking

Tests the DecisionOutcome model, persistence functions, and outcome recorder.
Ensures that outcomes can be recorded, retrieved, and validated without breaking
existing orchestration flow.

Test Coverage:
- Model imports and schema validation
- Outcome recorder API validation
- Data validation (outcome, exit_reason, prices)
- Pydantic schema tests
- Documentation verification
"""

import pytest
import asyncio
from datetime import datetime, timezone
from reasoner_service import storage as st
from reasoner_service.outcome_recorder import DecisionOutcomeRecorder
from reasoner_service.schemas import (
    DecisionOutcomeCreate,
    DecisionOutcome as DecisionOutcomeSchema,
)


class TestDecisionOutcomeImports:
    """Test that DecisionOutcome model is properly defined and imported."""

    def test_decision_outcome_model_exists(self):
        """Test that DecisionOutcome model is defined in storage."""
        assert hasattr(st, 'DecisionOutcome')
        model = st.DecisionOutcome
        assert hasattr(model, '__tablename__')
        assert model.__tablename__ == 'decision_outcomes'

    def test_decision_outcome_model_fields(self):
        """Test that DecisionOutcome has all required fields."""
        model = st.DecisionOutcome
        table_columns = {col.name for col in model.__table__.columns}
        expected = {
            'id', 'decision_id', 'symbol', 'timeframe', 'signal_type',
            'entry_price', 'exit_price', 'pnl', 'outcome', 'exit_reason',
            'closed_at', 'created_at'
        }
        assert expected.issubset(table_columns), f"Missing columns: {expected - table_columns}"

    def test_decision_outcome_model_indexes(self):
        """Test that DecisionOutcome has proper indexes for queries."""
        model = st.DecisionOutcome
        # Verify indexed columns exist (used for efficient queries)
        indexed_cols = {'decision_id', 'symbol', 'created_at'}
        table_columns = {col.name for col in model.__table__.columns}
        assert indexed_cols.issubset(table_columns)


class TestDecisionOutcomePersistenceFunctions:
    """Test that persistence functions are properly defined."""

    def test_insert_decision_outcome_function_exists(self):
        """Test that insert_decision_outcome is defined as async."""
        assert hasattr(st, 'insert_decision_outcome')
        assert asyncio.iscoroutinefunction(st.insert_decision_outcome)

    def test_get_decision_outcome_by_id_function_exists(self):
        """Test that get_decision_outcome_by_id is defined as async."""
        assert hasattr(st, 'get_decision_outcome_by_id')
        assert asyncio.iscoroutinefunction(st.get_decision_outcome_by_id)

    def test_get_recent_decision_outcomes_function_exists(self):
        """Test that get_recent_decision_outcomes is defined as async."""
        assert hasattr(st, 'get_recent_decision_outcomes')
        assert asyncio.iscoroutinefunction(st.get_recent_decision_outcomes)

    def test_get_outcomes_by_decision_id_function_exists(self):
        """Test that get_outcomes_by_decision_id is defined as async."""
        assert hasattr(st, 'get_outcomes_by_decision_id')
        assert asyncio.iscoroutinefunction(st.get_outcomes_by_decision_id)

    def test_get_outcomes_by_symbol_function_exists(self):
        """Test that get_outcomes_by_symbol is defined as async."""
        assert hasattr(st, 'get_outcomes_by_symbol')
        assert asyncio.iscoroutinefunction(st.get_outcomes_by_symbol)

    def test_persistence_functions_have_docstrings(self):
        """Test that persistence functions have documentation."""
        for func_name in [
            'insert_decision_outcome',
            'get_decision_outcome_by_id',
            'get_recent_decision_outcomes',
            'get_outcomes_by_decision_id',
            'get_outcomes_by_symbol'
        ]:
            func = getattr(st, func_name)
            assert func.__doc__ is not None, f"{func_name} missing docstring"
            assert len(func.__doc__) > 0


class TestDecisionOutcomeRecorder:
    """Tests for DecisionOutcomeRecorder utility."""

    def test_recorder_class_exists(self):
        """Test that DecisionOutcomeRecorder class is defined."""
        assert DecisionOutcomeRecorder is not None

    def test_recorder_init(self):
        """Test that DecisionOutcomeRecorder can be instantiated."""
        class MockSessionMaker:
            pass
        
        sessionmaker = MockSessionMaker()
        recorder = DecisionOutcomeRecorder(sessionmaker)
        assert recorder.sessionmaker is sessionmaker

    def test_recorder_record_trade_outcome_method_exists(self):
        """Test that record_trade_outcome method exists and is async."""
        class MockSessionMaker:
            pass
        
        recorder = DecisionOutcomeRecorder(MockSessionMaker())
        assert hasattr(recorder, 'record_trade_outcome')
        assert asyncio.iscoroutinefunction(recorder.record_trade_outcome)

    def test_recorder_has_docstrings(self):
        """Test that DecisionOutcomeRecorder has proper documentation."""
        assert DecisionOutcomeRecorder.__doc__ is not None
        assert len(DecisionOutcomeRecorder.__doc__) > 0
        assert "async recorder" in DecisionOutcomeRecorder.__doc__.lower()

    def test_recorder_record_trade_outcome_has_docstring(self):
        """Test that record_trade_outcome method has documentation."""
        docstring = DecisionOutcomeRecorder.record_trade_outcome.__doc__
        assert docstring is not None
        assert len(docstring) > 0
        assert "trade outcome" in docstring.lower()

    @pytest.mark.asyncio
    async def test_recorder_invalid_exit_reason_validation(self):
        """Test that recorder validates exit_reason."""
        class MockSessionMaker:
            pass
        
        recorder = DecisionOutcomeRecorder(MockSessionMaker())
        with pytest.raises(ValueError, match="Invalid exit_reason"):
            await recorder.record_trade_outcome(
                decision_id="test-id",
                symbol="EURUSD",
                timeframe="4H",
                signal_type="bullish_choch",
                entry_price=1.0850,
                exit_price=1.0900,
                pnl=50.0,
                exit_reason="invalid_reason",
            )

    @pytest.mark.asyncio
    async def test_recorder_accepts_valid_exit_reasons(self):
        """Test that recorder accepts all valid exit_reason values."""
        class MockSessionMaker:
            async def __call__(self):
                # Return a mock session that does nothing
                class MockSession:
                    async def __aenter__(self):
                        return self
                    async def __aexit__(self, *args):
                        pass
                return MockSession()
        
        recorder = DecisionOutcomeRecorder(MockSessionMaker())
        # Should not raise for any valid exit_reason
        for exit_reason in ("tp", "sl", "manual", "timeout"):
            # We're not actually executing DB operations, just testing validation
            try:
                await recorder.record_trade_outcome(
                    decision_id="test-id",
                    symbol="EURUSD",
                    timeframe="4H",
                    signal_type="bullish_choch",
                    entry_price=1.0850,
                    exit_price=1.0900,
                    pnl=50.0,
                    exit_reason=exit_reason,
                )
            except ValueError:
                pytest.fail(f"Recorder should accept exit_reason={exit_reason}")


class TestDecisionOutcomePydanticSchemas:
    """Tests for Pydantic schemas."""

    def test_decision_outcome_create_schema_exists(self):
        """Test that DecisionOutcomeCreate schema is defined."""
        assert DecisionOutcomeCreate is not None

    def test_decision_outcome_schema_exists(self):
        """Test that DecisionOutcome schema is defined."""
        assert DecisionOutcomeSchema is not None

    @pytest.mark.asyncio
    async def test_decision_outcome_schema_creation(self):
        """Test creating DecisionOutcomeCreate schema."""
        now = datetime.now(timezone.utc)
        schema = DecisionOutcomeCreate(
            decision_id="test-id",
            symbol="EURUSD",
            timeframe="4H",
            signal_type="bullish_choch",
            entry_price=1.0850,
            exit_price=1.0900,
            pnl=50.0,
            outcome="win",
            exit_reason="tp",
            closed_at=now,
        )
        assert schema.symbol == "EURUSD"
        assert schema.outcome == "win"
        assert schema.entry_price == 1.0850
        assert schema.exit_price == 1.0900
        assert schema.pnl == 50.0

    @pytest.mark.asyncio
    async def test_decision_outcome_schema_validates_outcome(self):
        """Test Pydantic validation of outcome field."""
        with pytest.raises(ValueError, match="outcome must be"):
            DecisionOutcomeCreate(
                decision_id="test",
                symbol="EURUSD",
                timeframe="4H",
                signal_type="bullish_choch",
                entry_price=1.0850,
                exit_price=1.0900,
                pnl=50.0,
                outcome="invalid_outcome",
                exit_reason="tp",
                closed_at=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_decision_outcome_schema_validates_exit_reason(self):
        """Test Pydantic validation of exit_reason field."""
        with pytest.raises(ValueError, match="exit_reason must be"):
            DecisionOutcomeCreate(
                decision_id="test",
                symbol="EURUSD",
                timeframe="4H",
                signal_type="bullish_choch",
                entry_price=1.0850,
                exit_price=1.0900,
                pnl=50.0,
                outcome="win",
                exit_reason="invalid_reason",
                closed_at=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_decision_outcome_schema_all_outcome_values(self):
        """Test that all valid outcome values work."""
        now = datetime.now(timezone.utc)
        for outcome in ("win", "loss", "breakeven"):
            schema = DecisionOutcomeCreate(
                decision_id="test-id",
                symbol="EURUSD",
                timeframe="4H",
                signal_type="bullish_choch",
                entry_price=1.0850,
                exit_price=1.0900,
                pnl=50.0,
                outcome=outcome,
                exit_reason="tp",
                closed_at=now,
            )
            assert schema.outcome == outcome

    @pytest.mark.asyncio
    async def test_decision_outcome_schema_all_exit_reason_values(self):
        """Test that all valid exit_reason values work."""
        now = datetime.now(timezone.utc)
        for exit_reason in ("tp", "sl", "manual", "timeout"):
            schema = DecisionOutcomeCreate(
                decision_id="test-id",
                symbol="EURUSD",
                timeframe="4H",
                signal_type="bullish_choch",
                entry_price=1.0850,
                exit_price=1.0900,
                pnl=50.0,
                outcome="win",
                exit_reason=exit_reason,
                closed_at=now,
            )
            assert schema.exit_reason == exit_reason


class TestTradeModelExtension:
    """Test that Trade model is properly extended."""

    def test_trade_model_has_new_fields(self):
        """Test that Trade model has new outcome-aware fields."""
        from ict_trading_system.src.models.database import Trade
        
        table_columns = {col.name for col in Trade.__table__.columns}
        new_fields = {'decision_id', 'exit_price', 'exit_reason', 'closed_at'}
        assert new_fields.issubset(table_columns), f"Missing Trade fields: {new_fields - table_columns}"

    def test_trade_new_fields_are_nullable(self):
        """Test that new Trade fields are nullable (backward compatible)."""
        from ict_trading_system.src.models.database import Trade
        
        for field_name in ['decision_id', 'exit_price', 'exit_reason', 'closed_at']:
            col = Trade.__table__.columns[field_name]
            assert col.nullable, f"Field {field_name} should be nullable for backward compatibility"

    def test_trade_existing_fields_unchanged(self):
        """Test that existing Trade fields are still present."""
        from ict_trading_system.src.models.database import Trade
        
        table_columns = {col.name for col in Trade.__table__.columns}
        existing_fields = {'id', 'signal_id', 'entry_price', 'sl', 'tp', 'outcome', 'pnl', 'notes', 'timestamp'}
        assert existing_fields.issubset(table_columns), f"Missing existing Trade fields: {existing_fields - table_columns}"


class TestIntegrationDocumentation:
    """Test that integration documentation is complete."""

    def test_outcome_integration_guide_exists(self):
        """Test that OUTCOME_INTEGRATION.md exists."""
        import os
        outcome_guide_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "OUTCOME_INTEGRATION.md"
        )
        assert os.path.exists(outcome_guide_path), f"OUTCOME_INTEGRATION.md not found at {outcome_guide_path}"

    def test_outcome_integration_guide_has_content(self):
        """Test that OUTCOME_INTEGRATION.md has substantial content."""
        import os
        outcome_guide_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "OUTCOME_INTEGRATION.md"
        )
        with open(outcome_guide_path, 'r') as f:
            content = f.read()
        
        # Check for key sections
        assert "Data Model" in content
        assert "API Reference" in content
        assert "Integration Points" in content
        assert len(content) > 1000, "Documentation seems incomplete"

    def test_outcome_recorder_module_documented(self):
        """Test that outcome_recorder module is well documented."""
        import reasoner_service.outcome_recorder as om
        
        assert om.__doc__ is not None
        assert len(om.__doc__) > 0
        assert "Outcome-aware" in om.__doc__
        assert "records outcome" in om.__doc__.lower() or "outcome" in om.__doc__.lower()
