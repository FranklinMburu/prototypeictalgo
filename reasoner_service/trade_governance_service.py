"""
Trade Governance Service

Evaluates whether a hypothetical trade would comply with strict risk and session governance rules.

CRITICAL DISCLAIMER: This component does NOT block trades or influence live decisions.
It provides analytical governance assessment only for monitoring and compliance purposes.

Governance evaluation includes:
- Daily trade count limits
- Daily loss limits (drawdown protection)
- Session/killzone windows (avoid trading in specific hours)
- Cooldown periods after losses
- Symbol/timeframe overtrading detection
- Exposure concentration checks

Results are informational only. No actual trade blocking occurs.
This component operates in shadow mode alongside live trading.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class TradeGovernanceService:
    """
    Evaluates trades against governance rules without blocking them.
    
    This service assesses whether a hypothetical trade would comply with
    governance rules, providing informational violation reports without
    affecting live trading behavior.
    
    CONSTRAINTS:
    - Read-only outcomes consumption
    - Deterministic violation assessment
    - No database writes
    - No learning or tuning
    - Fail-silent error handling
    - No influence on live decisions
    """
    
    def __init__(
        self,
        max_trades_per_day: int = 5,
        max_daily_loss: float = 500.0,
        killzone_hours: Optional[List[tuple]] = None,
        cooldown_minutes_after_loss: int = 30,
        max_trades_per_symbol: int = 3,
        max_trades_per_timeframe: int = 4,
        min_trade_spacing_minutes: int = 5,
    ):
        """
        Initialize governance service with configurable risk rules.
        
        Args:
            max_trades_per_day: Maximum number of trades allowed in a calendar day
            max_daily_loss: Maximum cumulative loss allowed before trading stops
            killzone_hours: List of (start_hour, end_hour) tuples to avoid trading
                           e.g., [(0, 8), (22, 24)] for overnight silence
            cooldown_minutes_after_loss: Minutes to wait after loss before trading again
            max_trades_per_symbol: Max trades on same symbol per day
            max_trades_per_timeframe: Max trades on same timeframe per day
            min_trade_spacing_minutes: Minimum minutes between consecutive trades
        """
        self.max_trades_per_day = max_trades_per_day
        self.max_daily_loss = max_daily_loss
        self.killzone_hours = killzone_hours or []
        self.cooldown_minutes_after_loss = cooldown_minutes_after_loss
        self.max_trades_per_symbol = max_trades_per_symbol
        self.max_trades_per_timeframe = max_trades_per_timeframe
        self.min_trade_spacing_minutes = min_trade_spacing_minutes
        
        # Runtime state: outcomes for evaluation
        self._outcomes = []
        self._last_evaluation_timestamp = None
    
    def add_outcomes(self, outcomes: List[Dict[str, Any]]) -> None:
        """
        Register historical outcomes for governance evaluation.
        
        Args:
            outcomes: List of trade outcome dictionaries with fields:
                     - symbol, timeframe, outcome_value, pnl, timestamp
        """
        try:
            if not isinstance(outcomes, list):
                logger.warning("Outcomes must be a list, skipping registration")
                return
            
            # Store a deep copy to prevent input mutation
            import copy
            self._outcomes = copy.deepcopy(outcomes)
            logger.debug(f"Registered {len(self._outcomes)} outcomes for governance")
        except Exception as e:
            logger.exception(f"Error registering outcomes: {e}")
            self._outcomes = []
    
    def evaluate_trade(self, trade_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether a hypothetical trade would comply with governance rules.
        
        Args:
            trade_context: Trade metadata dict with:
                - symbol (str): Trading symbol
                - timeframe (str): Timeframe (e.g., "1H", "15m")
                - timestamp (str or datetime): Trade timestamp (ISO format or datetime)
                - pnl_estimate (float, optional): Estimated PnL if executed
        
        Returns:
            {
                "allowed": bool,
                "violations": list[str],
                "explanation": str,
                "evaluated_at": str (ISO timestamp),
                "disclaimer": str,
            }
        """
        try:
            if not trade_context:
                return self._create_error_report(
                    "Trade context is empty. Cannot evaluate."
                )
            
            symbol = trade_context.get("symbol", "UNKNOWN")
            timeframe = trade_context.get("timeframe", "UNKNOWN")
            timestamp_val = trade_context.get("timestamp")
            
            if not timestamp_val:
                return self._create_error_report(
                    "Trade timestamp is missing. Cannot evaluate timing rules."
                )
            
            # Parse timestamp
            try:
                if isinstance(timestamp_val, str):
                    trade_time = datetime.fromisoformat(timestamp_val.replace('Z', '+00:00'))
                else:
                    trade_time = timestamp_val
            except Exception as e:
                return self._create_error_report(
                    f"Invalid timestamp format: {str(e)}"
                )
            
            # Collect all violations
            violations = []
            
            # Rule 1: Daily trade count
            daily_trades_count = self._count_daily_trades(trade_time)
            if daily_trades_count >= self.max_trades_per_day:
                violations.append(
                    f"Daily trade limit reached: {daily_trades_count} trades already executed today"
                )
            
            # Rule 2: Daily loss limit
            daily_loss = self._calculate_daily_loss(trade_time)
            if daily_loss <= -self.max_daily_loss:
                violations.append(
                    f"Daily loss limit exceeded: ${abs(daily_loss):.2f} loss already accrued today"
                )
            
            # Rule 3: Killzone hours
            if self._is_in_killzone(trade_time):
                violations.append(
                    f"Trade attempted during killzone: {trade_time.strftime('%H:%M %Z')}"
                )
            
            # Rule 4: Cooldown after loss
            last_loss_time = self._find_last_loss_time(trade_time)
            if last_loss_time:
                cooldown_end = last_loss_time + timedelta(minutes=self.cooldown_minutes_after_loss)
                if trade_time < cooldown_end:
                    minutes_remaining = int((cooldown_end - trade_time).total_seconds() / 60)
                    violations.append(
                        f"Cooldown period active: {minutes_remaining} minutes remaining after last loss"
                    )
            
            # Rule 5: Symbol overtrading
            symbol_count = self._count_daily_symbol_trades(symbol, trade_time)
            if symbol_count >= self.max_trades_per_symbol:
                violations.append(
                    f"Symbol trade limit reached: {symbol_count} trades on {symbol} today"
                )
            
            # Rule 6: Timeframe overtrading
            timeframe_count = self._count_daily_timeframe_trades(timeframe, trade_time)
            if timeframe_count >= self.max_trades_per_timeframe:
                violations.append(
                    f"Timeframe trade limit reached: {timeframe_count} trades on {timeframe} today"
                )
            
            # Rule 7: Minimum trade spacing
            last_trade_time = self._find_last_trade_time(trade_time)
            if last_trade_time:
                spacing_minutes = (trade_time - last_trade_time).total_seconds() / 60
                if spacing_minutes < self.min_trade_spacing_minutes:
                    violations.append(
                        f"Trade spacing violation: only {spacing_minutes:.1f}m since last trade (min {self.min_trade_spacing_minutes}m)"
                    )
            
            # Determine if allowed
            allowed = len(violations) == 0
            
            # Generate explanation
            explanation = self._generate_explanation(
                symbol=symbol,
                timeframe=timeframe,
                allowed=allowed,
                violations=violations,
                daily_trades=daily_trades_count,
                daily_loss=daily_loss,
            )
            
            return {
                "allowed": allowed,
                "violations": violations,
                "explanation": explanation,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This analysis is informational only. "
                    "Results do not influence live trading decisions."
                ),
            }
        
        except Exception as e:
            logger.exception(f"Error evaluating trade: {e}")
            return self._create_error_report(f"Evaluation error: {str(e)}")
    
    def evaluate_batch(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluate multiple hypothetical trades.
        
        Args:
            trades: List of trade context dictionaries
        
        Returns:
            List of governance assessment reports (one per trade)
        """
        try:
            if not isinstance(trades, list):
                logger.warning("Trades must be a list")
                return []
            
            results = []
            for trade in trades:
                result = self.evaluate_trade(trade)
                results.append(result)
            
            return results
        except Exception as e:
            logger.exception(f"Error evaluating batch: {e}")
            return []
    
    # Private helper methods
    
    def _count_daily_trades(self, reference_time: datetime) -> int:
        """Count trades executed on the same calendar day."""
        try:
            reference_date = reference_time.date()
            count = 0
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                if outcome_time and outcome_time.date() == reference_date:
                    count += 1
            
            return count
        except Exception as e:
            logger.debug(f"Error counting daily trades: {e}")
            return 0
    
    def _calculate_daily_loss(self, reference_time: datetime) -> float:
        """Calculate cumulative PnL for the day (losses are negative)."""
        try:
            reference_date = reference_time.date()
            daily_pnl = 0.0
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                if outcome_time and outcome_time.date() == reference_date:
                    pnl = outcome.get("pnl", 0.0)
                    daily_pnl += float(pnl)
            
            return daily_pnl
        except Exception as e:
            logger.debug(f"Error calculating daily loss: {e}")
            return 0.0
    
    def _is_in_killzone(self, trade_time: datetime) -> bool:
        """Check if trade is during a killzone hour."""
        try:
            hour = trade_time.hour
            
            for start_hour, end_hour in self.killzone_hours:
                if start_hour <= end_hour:
                    # Normal range (e.g., 0-8)
                    if start_hour <= hour < end_hour:
                        return True
                else:
                    # Wraparound range (e.g., 22-24 wraps to 0)
                    if hour >= start_hour or hour < end_hour:
                        return True
            
            return False
        except Exception as e:
            logger.debug(f"Error checking killzone: {e}")
            return False
    
    def _find_last_loss_time(self, reference_time: datetime) -> Optional[datetime]:
        """Find the most recent losing trade before reference time."""
        try:
            last_loss = None
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                if not outcome_time or outcome_time >= reference_time:
                    continue
                
                pnl = outcome.get("pnl", 0.0)
                if pnl < 0:  # Is a loss
                    if not last_loss or outcome_time > last_loss:
                        last_loss = outcome_time
            
            return last_loss
        except Exception as e:
            logger.debug(f"Error finding last loss: {e}")
            return None
    
    def _count_daily_symbol_trades(self, symbol: str, reference_time: datetime) -> int:
        """Count trades on the same symbol during the same day."""
        try:
            reference_date = reference_time.date()
            count = 0
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                outcome_symbol = outcome.get("symbol", "")
                
                if (outcome_time and outcome_time.date() == reference_date and
                    outcome_symbol == symbol):
                    count += 1
            
            return count
        except Exception as e:
            logger.debug(f"Error counting symbol trades: {e}")
            return 0
    
    def _count_daily_timeframe_trades(self, timeframe: str, reference_time: datetime) -> int:
        """Count trades on the same timeframe during the same day."""
        try:
            reference_date = reference_time.date()
            count = 0
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                outcome_tf = outcome.get("timeframe", "")
                
                if (outcome_time and outcome_time.date() == reference_date and
                    outcome_tf == timeframe):
                    count += 1
            
            return count
        except Exception as e:
            logger.debug(f"Error counting timeframe trades: {e}")
            return 0
    
    def _find_last_trade_time(self, reference_time: datetime) -> Optional[datetime]:
        """Find the most recent trade before reference time."""
        try:
            last_trade = None
            
            for outcome in self._outcomes:
                outcome_time = self._parse_timestamp(outcome.get("timestamp"))
                if not outcome_time or outcome_time >= reference_time:
                    continue
                
                if not last_trade or outcome_time > last_trade:
                    last_trade = outcome_time
            
            return last_trade
        except Exception as e:
            logger.debug(f"Error finding last trade: {e}")
            return None
    
    def _parse_timestamp(self, timestamp_val: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        try:
            if isinstance(timestamp_val, str):
                return datetime.fromisoformat(timestamp_val.replace('Z', '+00:00'))
            elif isinstance(timestamp_val, datetime):
                return timestamp_val
            return None
        except Exception:
            return None
    
    def _generate_explanation(
        self,
        symbol: str,
        timeframe: str,
        allowed: bool,
        violations: List[str],
        daily_trades: int,
        daily_loss: float,
    ) -> str:
        """Generate human-readable governance assessment explanation."""
        try:
            parts = []
            
            if allowed:
                parts.append(
                    f"Trade on {symbol} ({timeframe}) would comply with all governance rules. "
                    f"Status: {daily_trades}/{self.max_trades_per_day} daily trades. "
                    f"Daily PnL: ${daily_loss:.2f}. No violations detected."
                )
            else:
                parts.append(
                    f"Trade on {symbol} ({timeframe}) would violate governance rules."
                )
                if violations:
                    parts.append("Violations:")
                    for v in violations:
                        parts.append(f"  • {v}")
                parts.append(
                    f"Status: {daily_trades}/{self.max_trades_per_day} daily trades. "
                    f"Daily PnL: ${daily_loss:.2f}."
                )
            
            return " ".join(parts)
        except Exception as e:
            logger.debug(f"Error generating explanation: {e}")
            return "Unable to generate explanation."
    
    def _create_error_report(self, error_message: str) -> Dict[str, Any]:
        """Create an error report when evaluation fails."""
        return {
            "allowed": False,
            "violations": [error_message],
            "explanation": f"Evaluation error: {error_message}",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "This analysis is informational only. "
                "Results do not influence live trading decisions."
            ),
        }
