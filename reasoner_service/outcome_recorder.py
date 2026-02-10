"""
Outcome-aware Decision Tracking Recorder

This module provides the primary API for recording trade outcomes when trades close.
It bridges the gap between decision orchestration and outcome analysis, enabling
outcome-aware decision feedback without introducing learning logic yet.

The recorder follows async patterns consistent with DecisionOrchestrator and logs
integration points for future enhancements (PolicyStore refinement, ReasoningManager
feedback loops, etc.).

Future Integration Points:
1. PolicyStore: Use outcome patterns to refine killzone, regime, cooldown, exposure policies
2. ReasoningManager: Feed win/loss patterns back to reasoning functions for improvement
3. Observability: Enhance Prometheus metrics with per-signal-type win rate, PnL stats
4. EventTracker: Link outcomes to events in OrchestrationStateManager for lifecycle tracking
"""

import asyncio
from typing import Optional
from datetime import datetime, timezone
from logging import getLogger

# Import storage functions for persisting outcomes
from .storage import (
    insert_decision_outcome,
    DecisionOutcome as DecisionOutcomeModel,
)

logger = getLogger(__name__)


class DecisionOutcomeRecorder:
    """
    Async recorder for decision outcomes.
    
    Persists trade outcomes when trades close, maintaining a record of
    entry signals, pricing, P&L, and exit reasons.
    
    Non-blocking by design: errors in recording do not interrupt the
    main orchestration flow.
    """

    def __init__(self, sessionmaker):
        """
        Initialize the outcome recorder.
        
        Args:
            sessionmaker: Async SQLAlchemy sessionmaker bound to the database
        """
        self.sessionmaker = sessionmaker

    async def record_trade_outcome(
        self,
        decision_id: str,
        symbol: str,
        timeframe: str,
        signal_type: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        exit_reason: str = "manual",  # "tp", "sl", "manual", "timeout"
        closed_at: Optional[datetime] = None,
        model: str = None,
        session_id: str = None,
        direction: str = None,
        stop_loss_price: float = None,
        r_multiple: float = None,
    ) -> Optional[str]:
        """
        Record a trade outcome when a trade closes.
        
        This is the primary API for recording outcomes. It validates inputs,
        persists the outcome to the database, and logs integration points
        for future enhancement.
        
        Args:
            decision_id: UUID of the decision that triggered the entry
            symbol: Trading pair (e.g., "EURUSD")
            timeframe: Signal timeframe (e.g., "4H", "1D")
            signal_type: Signal type (e.g., "bullish_choch", "bearish_bos")
            entry_price: Price at entry
            exit_price: Price at exit
            pnl: Profit/loss amount (currency or pips)
            exit_reason: Reason for exit - "tp" (take profit), "sl" (stop loss),
                        "manual" (manually closed), "timeout" (time-based exit)
            closed_at: UTC timestamp when trade closed. Defaults to now().
            model: Optional AI model identifier
            session_id: Optional trading session identifier
            direction: Optional trade direction (\"long\" or \"short\")
            stop_loss_price: Optional stop loss price for r_multiple calculation
            r_multiple: Optional risk multiple (auto-computed if stop_loss_price provided)
        
        Returns:
            outcome_id: UUID of the DecisionOutcome record, or None on error
        
        Raises:
            ValueError: If inputs are invalid (e.g., invalid exit_reason or outcome)
            Exception: Propagated database errors (non-blocking, logged)
        
        Example:
            >>> recorder = DecisionOutcomeRecorder(sessionmaker)
            >>> outcome_id = await recorder.record_trade_outcome(
            ...     decision_id="uuid-123",
            ...     symbol="EURUSD",
            ...     timeframe="4H",
            ...     signal_type="bullish_choch",
            ...     entry_price=1.0850,
            ...     exit_price=1.0900,
            ...     pnl=50.0,
            ...     exit_reason="tp",            ...     model=\"v1\",
            ...     session_id=\"London\",
            ...     direction=\"long\",
            ...     r_multiple=2.5,            ... )
        """
        # Use current UTC time if not provided
        closed_at = closed_at or datetime.now(timezone.utc)

        # Determine outcome from PnL
        if pnl > 0:
            outcome = "win"
        elif pnl < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"
        
        # Compute r_multiple if not provided and stop_loss_price is available
        if r_multiple is None and stop_loss_price is not None:
            r_multiple = self._compute_r_multiple(
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss_price=stop_loss_price,
                direction=direction,
            )

        # Validate exit_reason
        valid_exit_reasons = ("tp", "sl", "manual", "timeout")
        if exit_reason not in valid_exit_reasons:
            raise ValueError(
                f"Invalid exit_reason '{exit_reason}'; must be one of {valid_exit_reasons}"
            )

        try:
            # Persist outcome to database
            outcome_id = await insert_decision_outcome(
                self.sessionmaker,
                decision_id=decision_id,
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                outcome=outcome,
                exit_reason=exit_reason,
                closed_at=closed_at,
                model=model,
                session_id=session_id,
                direction=direction,
                r_multiple=r_multiple,
            )

            logger.info(
                f"Recorded trade outcome: decision_id={decision_id} symbol={symbol} "
                f"outcome={outcome} pnl={pnl} exit_reason={exit_reason} r_multiple={r_multiple} id={outcome_id}"
            )

            # Log integration points for future enhancement
            # These are informational and non-blocking
            self._log_integration_points(
                outcome_id=outcome_id,
                decision_id=decision_id,
                symbol=symbol,
                signal_type=signal_type,
                outcome=outcome,
                pnl=pnl,
            )

            return outcome_id

        except ValueError as e:
            # Validation error - log and re-raise
            logger.error(f"Validation error recording outcome: {e}")
            raise
        except Exception as e:
            # Database error - log but don't raise (non-blocking)
            logger.error(
                f"Error recording outcome for decision_id={decision_id}: {e}",
                exc_info=True,
            )
            return None

    def _compute_r_multiple(
        self,
        entry_price: float,
        exit_price: float,
        stop_loss_price: float,
        direction: str = None,
    ) -> Optional[float]:
        """
        Compute risk multiple (reward/risk ratio) for a trade.
        
        Formula:
        - LONG:  (exit_price - entry_price) / (entry_price - stop_loss_price)
        - SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            stop_loss_price: Stop loss price
            direction: Trade direction ("long" or "short")
        
        Returns:
            r_multiple: Risk multiple (can be negative for losses), or None if computation fails
        """
        try:
            # Validate inputs
            if not all(v is not None and isinstance(v, (int, float)) for v in [entry_price, exit_price, stop_loss_price]):
                logger.warning(f"Cannot compute r_multiple: missing or invalid inputs (entry={entry_price}, exit={exit_price}, sl={stop_loss_price})")
                return None
            
            # Compute based on direction
            if direction and direction.lower() == "short":
                # SHORT: (entry_price - exit_price) / (stop_loss_price - entry_price)
                risk = stop_loss_price - entry_price
                if risk == 0:
                    logger.warning(f"Cannot compute r_multiple for SHORT: zero risk (entry={entry_price}, sl={stop_loss_price})")
                    return None
                reward = entry_price - exit_price
                r_mult = reward / risk
            else:
                # LONG (default): (exit_price - entry_price) / (entry_price - stop_loss_price)
                risk = entry_price - stop_loss_price
                if risk == 0:
                    logger.warning(f"Cannot compute r_multiple for LONG: zero risk (entry={entry_price}, sl={stop_loss_price})")
                    return None
                reward = exit_price - entry_price
                r_mult = reward / risk
            
            logger.debug(f"Computed r_multiple={r_mult:.2f} for direction={direction} entry={entry_price} exit={exit_price} sl={stop_loss_price}")
            return round(float(r_mult), 4)
        
        except Exception as e:
            logger.warning(f"Error computing r_multiple: {e}")
            return None

    def _log_integration_points(
        self,
        outcome_id: str,
        decision_id: str,
        symbol: str,
        signal_type: str,
        outcome: str,
        pnl: float,
    ) -> None:
        """
        Log integration points for future enhancements.
        
        These are informational logs that indicate where this outcome data
        will be used in future feature development.
        
        Future Integration Points:
        1. PolicyStore Refinement:
           - Track outcomes by symbol, signal_type to refine killzone/regime policies
           - Example: "EURUSD bearish_bos" has 65% win rate → adjust exposure policy
        
        2. ReasoningManager Feedback:
           - Use outcome patterns to retrain reasoning functions
           - Example: When confidence > 0.8 and signal_type="bullish_choch", win rate is 72%
        
        3. EventTracker Lifecycle:
           - Link outcome back to EventTracker entry for complete decision lifecycle
           - Update EventState from PROCESSED to CLOSED with final outcome
        
        4. Observability Enhancement:
           - Aggregate outcomes per symbol, signal_type for Prometheus metrics
           - Example: decisions_outcome_total{symbol="EURUSD", outcome="win"} += 1
        
        5. A/B Testing Framework (future):
           - Compare outcomes for different reasoning modes or policies
           - Example: Compare policy version A vs B for same signal patterns
        """
        logger.debug(
            f"[INTEGRATION] Outcome recorded (outcome_id={outcome_id}): "
            f"Decision {decision_id} → {outcome} (PnL={pnl}). "
            f"Symbol={symbol}, Signal={signal_type}. "
            f"Future: Use for PolicyStore refinement, ReasoningManager feedback, "
            f"EventTracker lifecycle update, and observability enhancement."
        )


async def create_outcome_recorder(sessionmaker) -> DecisionOutcomeRecorder:
    """
    Factory function to create a DecisionOutcomeRecorder.
    
    Args:
        sessionmaker: Async SQLAlchemy sessionmaker
    
    Returns:
        DecisionOutcomeRecorder instance
    """
    return DecisionOutcomeRecorder(sessionmaker)
