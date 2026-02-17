"""
Paper Trading Experiment Runner

Runs a controlled experiment feeding 50+ valid decisions through DecisionOrchestrator
with paper_execution_adapter and outcome_adaptation enabled. Collects metrics and
generates a FINAL REPORT.

Configuration (LOCKED):
- Symbol: EURUSD
- Timeframe: 4H
- Signal Type: bullish_choch
- Direction: long
- Model: v1
- Session: London
- Paper Adapter: enabled, zero slippage, instant TP/SL, seed=42
- Memory Recall Veto: enabled, expectancy_r=-0.05, win_rate=0.45, min_sample=20
"""

import asyncio
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.storage import (
    create_engine_from_env_or_dsn, create_engine_and_sessionmaker, 
    init_models, DecisionOutcome
)


# ============================================================================
# EXPERIMENT CONFIGURATION (LOCKED)
# ============================================================================

EXPERIMENT_CONFIG = {
    "symbol": "EURUSD",
    "timeframe": "4H",
    "signal_type": "bullish_choch",
    "direction": "long",
    "model": "v1",
    "session": "London",
    "target_closed_trades": 50,
}

# ============================================================================
# DECISION GENERATOR
# ============================================================================

def generate_test_decision(
    decision_id: Optional[str] = None,
    symbol: str = "EURUSD",
    signal_type: str = "bullish_choch",
    timeframe: str = "4H",
    direction: str = "long",
    model: str = "v1",
    session: str = "London",
    entry_price: float = 1.0850,
    stop_loss_price: float = 1.0800,
    take_profit_price: float = 1.0900,
) -> Dict[str, Any]:
    """Generate a valid test decision for paper trading."""
    
    return {
        "id": decision_id or str(uuid.uuid4()),
        "timestamp_ms": int(time.time() * 1000),
        "symbol": symbol,
        "timeframe": timeframe,
        "signal_type": signal_type,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "model": model,
        "session": session,
        "recommendation": "BUY",
        "confidence": 85.0,
        "confluence": {
            "confluent_signals": ["POI", "FVG", "mitigation"],
            "score": 85.0,
        },
        "htf_bias": "bullish",
        "ltf_bias": "bullish",
        "regime": "TREND",
    }


# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

class PaperTradingExperimentRunner:
    """Runs controlled paper trading experiment and collects metrics."""
    
    def __init__(self, dsn: str = "sqlite+aiosqlite:///:memory:"):
        self.dsn = dsn
        self.orchestrator: Optional[DecisionOrchestrator] = None
        self.decisions_seen: int = 0
        self.trades_executed: int = 0
        self.trades_vetoed: int = 0
        self.closed_outcomes: List[DecisionOutcome] = []
        self.veto_activated_after_trade: Optional[int] = None
        
    async def setup(self):
        """Initialize orchestrator and database."""
        # Create orchestrator with DSN
        self.orchestrator = DecisionOrchestrator(dsn=self.dsn)
        
        # Call orchestrator.setup() which handles async engine creation
        try:
            await self.orchestrator.setup()
        except Exception as e:
            print(f"Orchestrator setup error (may be expected): {e}")
            # Try manual setup as fallback
            engine, sessionmaker = await create_engine_and_sessionmaker(dsn=self.dsn)
            self.orchestrator.engine = engine
            self.orchestrator._sessionmaker = sessionmaker
            await init_models(engine)
        
    async def run_experiment(self) -> Dict[str, Any]:
        """Run experiment: feed decisions until 50 trades close."""
        
        await self.setup()
        
        trade_counter = 0  # Count of successfully executed paper trades (closed)
        decision_counter = 0
        
        # Generate and feed decisions
        while trade_counter < EXPERIMENT_CONFIG["target_closed_trades"]:
            decision_counter += 1
            self.decisions_seen = decision_counter
            
            # Create decision with slight price variation
            price_variation = 0.0001 * (decision_counter % 10)  # Small variation
            decision = generate_test_decision(
                entry_price=1.0850 + price_variation,
                stop_loss_price=1.0800 + price_variation,
                take_profit_price=1.0900 + price_variation,
            )
            
            # Process decision through orchestrator
            result = await self.orchestrator.process_decision(
                decision,
                persist=True,
                channels=["test_channel"]
            )
            
            # Check if decision was executed or vetoed
            if result.get("veto_result"):
                # Decision was vetoed (by any policy)
                veto_info = result.get("veto_result", {})
                if veto_info.get("reason") == "memory_recall":
                    self.trades_vetoed += 1
                    # Track when veto first activates
                    if self.veto_activated_after_trade is None:
                        self.veto_activated_after_trade = self.trades_executed
            else:
                # Decision was not vetoed; check if paper trade was executed
                if result.get("paper_trade_executed"):
                    self.trades_executed += 1
            
            # Query closed trades from database
            self.closed_outcomes = self._query_closed_trades()
            trade_counter = len(self.closed_outcomes)
            
            # Timeout safeguard: break after max decisions if trades not closing
            if decision_counter > 500:
                print(f"WARNING: Reached 500 decisions with only {trade_counter} closed trades")
                break
            
            # Log progress every 10 decisions
            if decision_counter % 10 == 0:
                print(f"Progress: {decision_counter} decisions, {trade_counter} closed trades")
        
        print(f"\nExperiment complete:")
        print(f"  Total decisions: {self.decisions_seen}")
        print(f"  Closed trades: {len(self.closed_outcomes)}")
        
        return self._compute_metrics()
    
    def _query_closed_trades(self) -> List[DecisionOutcome]:
        """Query all closed trades from database."""
        if not self.orchestrator._sessionmaker:
            return []
        
        with self.orchestrator._sessionmaker() as session:
            outcomes = session.query(DecisionOutcome).filter(
                DecisionOutcome.symbol == EXPERIMENT_CONFIG["symbol"],
                DecisionOutcome.signal_type == EXPERIMENT_CONFIG["signal_type"],
                DecisionOutcome.model == EXPERIMENT_CONFIG["model"],
                DecisionOutcome.session_id == EXPERIMENT_CONFIG["session"],
                DecisionOutcome.direction == EXPERIMENT_CONFIG["direction"],
                DecisionOutcome.outcome.isnot(None),  # Only closed trades
                DecisionOutcome.r_multiple.isnot(None),  # Only with r_multiple
            ).all()
            return outcomes
    
    def _compute_metrics(self) -> Dict[str, Any]:
        """Compute performance metrics from closed trades."""
        
        outcomes = self.closed_outcomes
        
        if not outcomes:
            return {
                "total_decisions_seen": self.decisions_seen,
                "trades_executed": self.trades_executed,
                "trades_vetoed": self.trades_vetoed,
                "expectancy": None,
                "win_rate": None,
                "max_loss_streak": 0,
                "trade_count_before_veto_trigger": self.veto_activated_after_trade,
                "closed_trades": 0,
            }
        
        # Extract r_multiple values
        r_multiples = [float(o.r_multiple) for o in outcomes if o.r_multiple is not None]
        outcomes_list = [o.outcome for o in outcomes]
        
        # Compute expectancy (mean r_multiple)
        expectancy = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
        
        # Compute win rate
        wins = sum(1 for outcome in outcomes_list if outcome == "win")
        win_rate = wins / len(outcomes_list) if outcomes_list else 0.0
        
        # Compute max loss streak
        max_loss_streak = self._compute_max_loss_streak(outcomes_list)
        
        return {
            "total_decisions_seen": self.decisions_seen,
            "trades_executed": self.trades_executed,
            "trades_vetoed": self.trades_vetoed,
            "expectancy": expectancy,
            "win_rate": win_rate,
            "max_loss_streak": max_loss_streak,
            "trade_count_before_veto_trigger": self.veto_activated_after_trade,
            "closed_trades": len(outcomes),
        }
    
    def _compute_max_loss_streak(self, outcomes: List[str]) -> int:
        """Compute maximum consecutive losses."""
        if not outcomes:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for outcome in outcomes:
            if outcome == "loss":
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    async def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate FINAL REPORT in exact format."""
        
        report = f"""
=== PAPER TRADING REPORT ===
Symbol: {EXPERIMENT_CONFIG["symbol"]}
Timeframe: {EXPERIMENT_CONFIG["timeframe"]}
Signal Type: {EXPERIMENT_CONFIG["signal_type"]}
Seed: 42

Decisions Seen: {metrics["total_decisions_seen"]}
Trades Executed: {metrics["trades_executed"]}
Trades Vetoed (Memory Recall): {metrics["trades_vetoed"]}

Expectancy (R): {metrics["expectancy"]:.4f if metrics["expectancy"] is not None else "N/A"}
Win Rate: {metrics["win_rate"]:.4f if metrics["win_rate"] is not None else "N/A"}
Max Loss Streak: {metrics["max_loss_streak"]}
Memory Veto Activated After N Trades: {metrics["trade_count_before_veto_trigger"] if metrics["trade_count_before_veto_trigger"] is not None else "Not activated"}

=== END REPORT ===
"""
        return report


# ============================================================================
# PYTEST TEST FUNCTION
# ============================================================================

@pytest.mark.asyncio
async def test_paper_trading_experiment():
    """Run controlled paper trading experiment."""
    
    # Create runner
    runner = PaperTradingExperimentRunner()
    
    # Run experiment
    metrics = await runner.run_experiment()
    
    # Generate and print report
    report = await runner.generate_report(metrics)
    print("\n" + report)
    
    # Assert basic success criteria
    assert metrics["closed_trades"] >= 50, f"Expected 50+ closed trades, got {metrics['closed_trades']}"
    assert metrics["expectancy"] is not None, "Expectancy should not be None"
    assert 0.0 <= metrics["win_rate"] <= 1.0, f"Win rate should be in [0,1], got {metrics['win_rate']}"
    
    # Store report for external access
    runner.final_report = report
    runner.final_metrics = metrics


# ============================================================================
# STANDALONE RUNNER (Can be run directly)
# ============================================================================

async def main():
    """Run experiment standalone."""
    runner = PaperTradingExperimentRunner()
    metrics = await runner.run_experiment()
    report = await runner.generate_report(metrics)
    print(report)
    return metrics


if __name__ == "__main__":
    # Run standalone
    asyncio.run(main())
