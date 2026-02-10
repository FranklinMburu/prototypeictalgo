"""
Paper Execution Adapter - Deterministic Trade Simulation

SCOPE:
- Simulates order execution (fill price, slippage, TP/SL hit)
- Produces trade outcomes with r_multiple
- Bridges decision→outcome loop without live broker
- Feature-flagged OFF by default
- NO intelligence, NO tuning, NO randomness (unless seeded)

PURPOSE:
Enable paper trading performance attribution to validate:
1. Decision veto logic correctness
2. r_multiple computation accuracy
3. Memory recall veto effectiveness
4. Expectancy calculation on realistic trade flow

DESIGN PRINCIPLES:
- Deterministic: Same inputs + seed → same outputs
- Configurable: Slippage model, TP/SL model, fill timing
- Fail-open: Errors return default outcome (no crash)
- Non-blocking: Adapter errors don't interrupt orchestration
"""

import asyncio
import random
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from logging import getLogger

logger = getLogger(__name__)


class SlippageModel(Enum):
    """Models for simulating market slippage on fill."""
    ZERO = "zero"              # No slippage (ideal fill)
    FIXED_PERCENT = "fixed_percent"  # Fixed % slippage (e.g., 0.1%)
    RANDOM_BOUNDED = "random_bounded"  # Random within bounds (e.g., 0-0.2%)


class TPSLModel(Enum):
    """Models for simulating take-profit and stop-loss hit."""
    INSTANT = "instant"        # Hit immediately (unrealistic but fast)
    RANDOM_BARS = "random_bars"  # Hit within N candles (configurable)
    RANDOM_HOURS = "random_hours"  # Hit within N hours (configurable)


@dataclass
class PaperExecutionConfig:
    """Configuration for paper execution simulation."""
    
    # Slippage model
    slippage_model: str = "fixed_percent"
    slippage_fixed_pct: float = 0.05  # 0.05% = 0.0005 multiplier
    slippage_random_min_pct: float = 0.0
    slippage_random_max_pct: float = 0.1
    
    # TP/SL model
    tpsl_model: str = "random_bars"
    tpsl_random_bars_min: int = 5  # Min candles until hit
    tpsl_random_bars_max: int = 100  # Max candles until hit
    tpsl_random_hours_min: int = 1
    tpsl_random_hours_max: int = 24
    
    # Fill assumptions
    assume_fill_on_signal: bool = True  # Fill immediately or with delay
    fill_delay_seconds: int = 2  # Delay before fill (if not immediate)
    
    # Random seed for determinism
    seed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dict for logging."""
        return asdict(self)


@dataclass
class PaperExecutionResult:
    """Result of a simulated paper trade execution."""
    
    # Decision/Intent metadata
    decision_id: str
    symbol: str
    signal_type: str
    timeframe: str
    direction: str  # "long" or "short"
    
    # Entry execution
    entry_price: float
    fill_price: float  # Actual fill with slippage
    slippage_amount: float  # fill_price - entry_price (signed)
    fill_time: datetime
    
    # Exit execution
    exit_price: float
    exit_time: datetime
    exit_reason: str  # "tp", "sl", "timeout", "manual"
    
    # Outcome metrics
    pnl: float  # In currency (or pips)
    outcome: str  # "win", "loss", "breakeven"
    r_multiple: Optional[float]  # Risk/reward ratio
    
    # Trade parameters
    stop_loss_price: float
    take_profit_price: float
    
    # Metadata
    model: Optional[str] = None
    session: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_outcome_recorder_args(self) -> Dict[str, Any]:
        """Convert to arguments for outcome_recorder.record_trade_outcome()."""
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "signal_type": self.signal_type,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "exit_reason": self.exit_reason,
            "closed_at": self.exit_time,
            "model": self.model,
            "session_id": self.session,
            "direction": self.direction,
            "stop_loss_price": self.stop_loss_price,
            "r_multiple": self.r_multiple,
        }


class BrokerSimulatorAdapter:
    """
    Simulates broker execution for paper trading.
    
    Usage:
        adapter = BrokerSimulatorAdapter(config)
        result = await adapter.execute_entry(
            decision_id="uuid",
            symbol="EURUSD",
            signal_type="bullish_choch",
            entry_price=1.0850,
            sl_price=1.0800,
            tp_price=1.0900,
            direction="long"
        )
        # result.to_outcome_recorder_args() → args for record_trade_outcome()
    """
    
    def __init__(self, config: Optional[PaperExecutionConfig] = None):
        """
        Initialize adapter with configuration.
        
        Args:
            config: PaperExecutionConfig; if None, uses defaults
        """
        self.config = config or PaperExecutionConfig()
        if self.config.seed is not None:
            random.seed(self.config.seed)
        logger.info(f"BrokerSimulatorAdapter initialized with config: {self.config.to_dict()}")
    
    async def execute_entry(
        self,
        decision_id: str,
        symbol: str,
        signal_type: str,
        timeframe: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        direction: str = "long",
        model: Optional[str] = None,
        session: Optional[str] = None,
    ) -> PaperExecutionResult:
        """
        Simulate entry execution and exit to produce complete trade result.
        
        Args:
            decision_id: UUID of the decision
            symbol: Trading pair (e.g., "EURUSD")
            signal_type: Signal type (e.g., "bullish_choch")
            timeframe: Timeframe (e.g., "4H")
            entry_price: Reference entry price (before slippage)
            sl_price: Stop loss price
            tp_price: Take profit price
            direction: "long" or "short"
            model: Optional model identifier
            session: Optional session identifier
        
        Returns:
            PaperExecutionResult with all trade details and r_multiple
        """
        try:
            # Step 1: Simulate entry fill
            fill_price, slippage_amount = self._simulate_entry_fill(entry_price, direction)
            fill_time = self._get_fill_time()
            
            # Step 2: Simulate exit (TP/SL/timeout)
            exit_price, exit_time, exit_reason = self._simulate_exit(
                fill_price, sl_price, tp_price, direction
            )
            
            # Step 3: Calculate outcome
            if direction.lower() == "short":
                pnl = (entry_price - exit_price)  # Simplified: no account size
            else:
                pnl = (exit_price - entry_price)
            
            outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
            
            # Step 4: Compute r_multiple
            r_multiple = self._compute_r_multiple(
                entry_price=fill_price,
                exit_price=exit_price,
                stop_loss_price=sl_price,
                direction=direction,
            )
            
            result = PaperExecutionResult(
                decision_id=decision_id,
                symbol=symbol,
                signal_type=signal_type,
                timeframe=timeframe,
                direction=direction,
                entry_price=entry_price,
                fill_price=fill_price,
                slippage_amount=slippage_amount,
                fill_time=fill_time,
                exit_price=exit_price,
                exit_time=exit_time,
                exit_reason=exit_reason,
                pnl=pnl,
                outcome=outcome,
                r_multiple=r_multiple,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                model=model,
                session=session,
            )
            
            logger.info(
                f"Paper trade executed: {symbol}/{signal_type} {direction} "
                f"entry={fill_price:.4f} exit={exit_price:.4f} pnl={pnl:.2f} r={r_multiple} outcome={outcome}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Paper trade execution failed: {e}", exc_info=True)
            # Return fail-open with worst-case outcome
            now = datetime.now(timezone.utc)
            worst_pnl = -100.0  # Default worst case
            if entry_price is not None and sl_price is not None:
                worst_pnl = -(abs(entry_price - sl_price))
            return PaperExecutionResult(
                decision_id=decision_id,
                symbol=symbol,
                signal_type=signal_type,
                timeframe=timeframe,
                direction=direction,
                entry_price=entry_price or 0.0,
                fill_price=entry_price or 0.0,
                slippage_amount=0.0,
                fill_time=now,
                exit_price=sl_price or 0.0,
                exit_time=now + timedelta(hours=1),
                exit_reason="manual",
                pnl=worst_pnl,
                outcome="loss",
                r_multiple=-1.0,
                stop_loss_price=sl_price or 0.0,
                take_profit_price=tp_price or 0.0,
                model=model,
                session=session,
            )
    
    def _simulate_entry_fill(self, entry_price: float, direction: str) -> tuple:
        """
        Simulate entry fill with slippage.
        
        Returns:
            (fill_price, slippage_amount) where slippage_amount is signed
        """
        if entry_price is None:
            return entry_price, 0.0
        
        slippage_pct = self._get_slippage_pct()
        
        # Slippage direction: worse fill for entry
        # LONG: slippage makes fill higher (we overpay) → negative slippage
        # SHORT: slippage makes fill lower (we get worse price) → negative slippage
        if direction.lower() == "short":
            slippage_amount = -entry_price * slippage_pct
        else:
            slippage_amount = entry_price * slippage_pct
        
        fill_price = entry_price + slippage_amount
        return fill_price, slippage_amount
    
    def _get_slippage_pct(self) -> float:
        """Get slippage percentage based on configured model."""
        model = self.config.slippage_model.lower()
        
        if model == "zero":
            return 0.0
        elif model == "fixed_percent":
            return self.config.slippage_fixed_pct / 100.0
        elif model == "random_bounded":
            min_pct = self.config.slippage_random_min_pct / 100.0
            max_pct = self.config.slippage_random_max_pct / 100.0
            return random.uniform(min_pct, max_pct)
        else:
            logger.warning(f"Unknown slippage model '{model}', defaulting to fixed_percent")
            return self.config.slippage_fixed_pct / 100.0
    
    def _get_fill_time(self) -> datetime:
        """Get fill time based on config."""
        now = datetime.now(timezone.utc)
        if self.config.assume_fill_on_signal:
            return now
        else:
            return now + timedelta(seconds=self.config.fill_delay_seconds)
    
    def _simulate_exit(
        self,
        fill_price: float,
        sl_price: float,
        tp_price: float,
        direction: str,
    ) -> tuple:
        """
        Simulate exit by checking if SL/TP is hit.
        
        Returns:
            (exit_price, exit_time, exit_reason)
        """
        now = datetime.now(timezone.utc)
        
        # Determine which level is hit first
        # For simplicity: randomly select between SL and TP hit (no walk simulation)
        # More realistic: could model price walk, but for determinism use bounded random
        
        model = self.config.tpsl_model.lower()
        
        if model == "instant":
            # 70% TP, 30% SL (survivorship bias, but simple for testing)
            if random.random() < 0.7:
                return tp_price, now + timedelta(hours=1), "tp"
            else:
                return sl_price, now + timedelta(hours=0.5), "sl"
        
        elif model == "random_bars":
            # Random number of bars until hit
            bars_until_hit = random.randint(
                self.config.tpsl_random_bars_min,
                self.config.tpsl_random_bars_max
            )
            # Assume 1H bars
            exit_time = now + timedelta(hours=bars_until_hit)
            
            # Decide SL vs TP (weighted)
            if random.random() < 0.7:
                return tp_price, exit_time, "tp"
            else:
                return sl_price, exit_time, "sl"
        
        elif model == "random_hours":
            # Random hours until hit
            hours_until_hit = random.randint(
                self.config.tpsl_random_hours_min,
                self.config.tpsl_random_hours_max
            )
            exit_time = now + timedelta(hours=hours_until_hit)
            
            if random.random() < 0.7:
                return tp_price, exit_time, "tp"
            else:
                return sl_price, exit_time, "sl"
        
        else:
            logger.warning(f"Unknown TPSL model '{model}', defaulting to instant")
            if random.random() < 0.7:
                return tp_price, now + timedelta(hours=1), "tp"
            else:
                return sl_price, now + timedelta(hours=0.5), "sl"
    
    def _compute_r_multiple(
        self,
        entry_price: float,
        exit_price: float,
        stop_loss_price: float,
        direction: str,
    ) -> Optional[float]:
        """Compute r_multiple (risk/reward ratio) for the trade."""
        try:
            if direction.lower() == "short":
                risk = stop_loss_price - entry_price
                if risk == 0:
                    return None
                reward = entry_price - exit_price
                r_mult = reward / risk
            else:
                risk = entry_price - stop_loss_price
                if risk == 0:
                    return None
                reward = exit_price - entry_price
                r_mult = reward / risk
            
            return round(float(r_mult), 4)
        
        except Exception as e:
            logger.warning(f"Error computing r_multiple: {e}")
            return None


async def create_paper_adapter(config: Optional[PaperExecutionConfig] = None) -> BrokerSimulatorAdapter:
    """
    Factory function to create a paper execution adapter.
    
    Args:
        config: Optional PaperExecutionConfig
    
    Returns:
        BrokerSimulatorAdapter instance
    """
    return BrokerSimulatorAdapter(config)
