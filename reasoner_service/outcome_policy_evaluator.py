"""
Outcome-aware Policy Evaluator

Consumes outcome statistics and applies deterministic policy rules to enable/disable
trading signals based on observable performance metrics. This is policy *feedback*,
not learning — all rules are static and configurable.

Key Design:
- Deterministic: Same inputs → Same outputs, no randomness
- Auditable: Every VETO is logged with structured reason
- Non-Adaptive: No parameter tuning or learning loops
- Read-Only: No database writes, only queries via OutcomeStatsService
- Pluggable: Rules are composable and configurable

Integration Model:
1. OutcomeStatsService queries DecisionOutcome table
2. OutcomePolicyEvaluator receives stats
3. Evaluator applies static rules (thresholds, streaks, etc.)
4. Returns ALLOW or VETO with structured audit information
5. DecisionOrchestrator or PolicyStore consumes decision

Future Integration Points:
1. PolicyStore: Can query OutcomePolicyEvaluator for dynamic policy decisions
2. SignalFilter: Can use VETO reasons to suppress signal types
3. PlanExecutor: Can honor VETO to prevent trade execution
4. Observability: Can export VETO counts per signal type

Non-Breaking Design:
- No changes to DecisionOrchestrator
- No changes to Pine Script
- No changes to ReasoningManager
- No changes to PlanExecutor
- Purely advisory until integrated into policy gates
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from logging import getLogger
from dataclasses import dataclass, asdict
from enum import Enum

from .outcome_stats import OutcomeStatsService

logger = getLogger(__name__)


class PolicyDecision(Enum):
    """Outcome of policy evaluation."""
    ALLOW = "allow"
    VETO = "veto"


@dataclass
class PolicyEvaluation:
    """Result of policy evaluation for a signal/symbol/timeframe."""
    
    decision: PolicyDecision
    """ALLOW or VETO"""
    
    reason: str
    """Human-readable reason for the decision"""
    
    rule_name: str
    """Name of the rule that made the decision (e.g., 'win_rate_threshold')"""
    
    signal_type: Optional[str] = None
    """Signal type being evaluated (e.g., 'bullish_choch')"""
    
    symbol: Optional[str] = None
    """Trading pair being evaluated (e.g., 'EURUSD')"""
    
    timeframe: Optional[str] = None
    """Timeframe being evaluated (e.g., '4H')"""
    
    metrics_snapshot: Optional[Dict[str, Any]] = None
    """Snapshot of outcome metrics used in evaluation"""
    
    timestamp: datetime = None
    """UTC timestamp of evaluation"""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "rule_name": self.rule_name,
            "signal_type": self.signal_type,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metrics": self.metrics_snapshot,
        }


class PolicyRule:
    """Base class for composable policy rules."""
    
    def __init__(self, name: str):
        """
        Initialize rule.
        
        Args:
            name: Unique name for this rule (e.g., 'win_rate_threshold')
        """
        self.name = name
    
    async def evaluate(
        self,
        stats_service: OutcomeStatsService,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Evaluate the rule against outcome stats.
        
        Args:
            stats_service: OutcomeStatsService instance
            signal_type: Signal type to evaluate (optional)
            symbol: Symbol to evaluate (optional)
            timeframe: Timeframe to evaluate (optional)
        
        Returns:
            PolicyEvaluation if rule fires (VETO or decision), None if N/A
        """
        raise NotImplementedError


class WinRateThresholdRule(PolicyRule):
    """Veto signals with win rate below threshold."""
    
    def __init__(
        self,
        name: str = "win_rate_threshold",
        min_win_rate: float = 0.45,
        min_trades: int = 10,
    ):
        """
        Initialize win rate threshold rule.
        
        Args:
            name: Rule name
            min_win_rate: Minimum acceptable win rate (0.0-1.0)
            min_trades: Minimum number of trades to evaluate (insufficient data → ALLOW)
        """
        super().__init__(name)
        if not (0.0 <= min_win_rate <= 1.0):
            raise ValueError(f"min_win_rate must be 0.0-1.0, got {min_win_rate}")
        self.min_win_rate = min_win_rate
        self.min_trades = min_trades
    
    async def evaluate(
        self,
        stats_service: OutcomeStatsService,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Evaluate signal's win rate against minimum threshold.
        
        VETO Decision Logic:
        - Insufficient data (< min_trades) → ALLOW (conservatively permit)
        - win_rate < min_win_rate → VETO
        - Otherwise → ALLOW (return None, rule doesn't fire)
        """
        try:
            # Get aggregated stats
            stats = await stats_service.aggregate_by_signal_type(
                symbol=symbol,
                timeframe=timeframe,
            )
            
            if not stats or signal_type not in stats:
                # No data for this signal type → ALLOW (insufficient data)
                return None
            
            sig_stats = stats[signal_type]
            count = sig_stats.get("count", 0)
            win_rate = sig_stats.get("win_rate", 0.0)
            
            logger.debug(
                f"evaluating_win_rate_rule",
                extra={
                    "rule": self.name,
                    "signal_type": signal_type,
                    "count": count,
                    "win_rate": win_rate,
                    "min_threshold": self.min_win_rate,
                },
            )
            
            # Insufficient data → ALLOW
            if count < self.min_trades:
                logger.debug(
                    f"rule_insufficient_data",
                    extra={
                        "rule": self.name,
                        "signal_type": signal_type,
                        "count": count,
                        "min_required": self.min_trades,
                    },
                )
                return None
            
            # Check threshold
            if win_rate < self.min_win_rate:
                reason = f"{signal_type} win rate {win_rate:.2%} below minimum {self.min_win_rate:.2%} ({count} trades)"
                logger.warning(
                    f"policy_veto",
                    extra={
                        "rule": self.name,
                        "decision": "VETO",
                        "reason": reason,
                        "signal_type": signal_type,
                    },
                )
                return PolicyEvaluation(
                    decision=PolicyDecision.VETO,
                    reason=reason,
                    rule_name=self.name,
                    signal_type=signal_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    metrics_snapshot=sig_stats,
                )
            
            return None
        except Exception as e:
            logger.error(f"Error evaluating win_rate_threshold rule: {e}", exc_info=True)
            return None


class LossStreakRule(PolicyRule):
    """Veto signals with excessive consecutive losses."""
    
    def __init__(
        self,
        name: str = "loss_streak",
        max_streak: int = 5,
    ):
        """
        Initialize loss streak rule.
        
        Args:
            name: Rule name
            max_streak: Maximum consecutive losses before veto
        """
        super().__init__(name)
        if max_streak < 1:
            raise ValueError(f"max_streak must be >= 1, got {max_streak}")
        self.max_streak = max_streak
    
    async def evaluate(
        self,
        stats_service: OutcomeStatsService,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Veto if current loss streak exceeds maximum.
        
        VETO Decision Logic:
        - No loss streak data → ALLOW (insufficient history)
        - current_streak > max_streak → VETO
        - Otherwise → ALLOW (return None)
        """
        try:
            streaks = await stats_service.get_loss_streak(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
            )
            
            if not streaks:
                # No data → ALLOW
                return None
            
            current_streak = streaks.get("current", 0)
            
            logger.debug(
                f"evaluating_loss_streak_rule",
                extra={
                    "rule": self.name,
                    "signal_type": signal_type,
                    "current_streak": current_streak,
                    "max_streak": self.max_streak,
                },
            )
            
            if current_streak > self.max_streak:
                reason = f"{signal_type} loss streak {current_streak} exceeds maximum {self.max_streak}"
                logger.warning(
                    f"policy_veto",
                    extra={
                        "rule": self.name,
                        "decision": "VETO",
                        "reason": reason,
                        "signal_type": signal_type,
                    },
                )
                return PolicyEvaluation(
                    decision=PolicyDecision.VETO,
                    reason=reason,
                    rule_name=self.name,
                    signal_type=signal_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    metrics_snapshot=streaks,
                )
            
            return None
        except Exception as e:
            logger.error(f"Error evaluating loss_streak rule: {e}", exc_info=True)
            return None


class AvgPnLThresholdRule(PolicyRule):
    """Veto signals with negative expected value (avg PnL)."""
    
    def __init__(
        self,
        name: str = "avg_pnl_threshold",
        min_avg_pnl: float = 0.0,
        min_trades: int = 10,
    ):
        """
        Initialize average P&L threshold rule.
        
        Args:
            name: Rule name
            min_avg_pnl: Minimum acceptable average P&L per trade
            min_trades: Minimum trades for evaluation (insufficient data → ALLOW)
        """
        super().__init__(name)
        self.min_avg_pnl = min_avg_pnl
        self.min_trades = min_trades
    
    async def evaluate(
        self,
        stats_service: OutcomeStatsService,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Veto if average P&L is below threshold.
        
        VETO Decision Logic:
        - Insufficient data → ALLOW
        - avg_pnl < min_avg_pnl → VETO
        - Otherwise → ALLOW
        """
        try:
            stats = await stats_service.aggregate_by_signal_type(
                symbol=symbol,
                timeframe=timeframe,
            )
            
            if not stats or signal_type not in stats:
                return None
            
            sig_stats = stats[signal_type]
            count = sig_stats.get("count", 0)
            avg_pnl = sig_stats.get("avg_pnl", 0.0)
            
            logger.debug(
                f"evaluating_avg_pnl_rule",
                extra={
                    "rule": self.name,
                    "signal_type": signal_type,
                    "avg_pnl": avg_pnl,
                    "min_threshold": self.min_avg_pnl,
                    "count": count,
                },
            )
            
            # Insufficient data → ALLOW
            if count < self.min_trades:
                return None
            
            if avg_pnl < self.min_avg_pnl:
                reason = f"{signal_type} avg PnL {avg_pnl:.2f} below minimum {self.min_avg_pnl:.2f} ({count} trades)"
                logger.warning(
                    f"policy_veto",
                    extra={
                        "rule": self.name,
                        "decision": "VETO",
                        "reason": reason,
                        "signal_type": signal_type,
                    },
                )
                return PolicyEvaluation(
                    decision=PolicyDecision.VETO,
                    reason=reason,
                    rule_name=self.name,
                    signal_type=signal_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    metrics_snapshot=sig_stats,
                )
            
            return None
        except Exception as e:
            logger.error(f"Error evaluating avg_pnl_threshold rule: {e}", exc_info=True)
            return None


class SymbolDrawdownRule(PolicyRule):
    """Veto signals if symbol has exceeded max drawdown."""
    
    def __init__(
        self,
        name: str = "symbol_drawdown",
        max_drawdown: float = -100.0,  # Negative value; e.g., -100 means -$100
        min_trades: int = 5,
    ):
        """
        Initialize symbol drawdown rule.
        
        Args:
            name: Rule name
            max_drawdown: Maximum acceptable total PnL for symbol (negative value)
            min_trades: Minimum trades for evaluation
        """
        super().__init__(name)
        self.max_drawdown = max_drawdown
        self.min_trades = min_trades
    
    async def evaluate(
        self,
        stats_service: OutcomeStatsService,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Veto if symbol's total PnL is below drawdown threshold.
        
        Useful for circuit-breaker: "Stop trading EURUSD if it's lost $500 today"
        """
        try:
            if not symbol:
                # Rule only applies when symbol is specified
                return None
            
            stats = await stats_service.aggregate_by_symbol(
                timeframe=timeframe,
                signal_type=signal_type,
            )
            
            if not stats or symbol not in stats:
                return None
            
            sym_stats = stats[symbol]
            count = sym_stats.get("count", 0)
            total_pnl = sym_stats.get("total_pnl", 0.0)
            
            logger.debug(
                f"evaluating_drawdown_rule",
                extra={
                    "rule": self.name,
                    "symbol": symbol,
                    "total_pnl": total_pnl,
                    "max_drawdown": self.max_drawdown,
                    "count": count,
                },
            )
            
            if count < self.min_trades:
                return None
            
            if total_pnl < self.max_drawdown:
                reason = f"{symbol} total PnL {total_pnl:.2f} exceeds drawdown limit {self.max_drawdown:.2f} ({count} trades)"
                logger.warning(
                    f"policy_veto",
                    extra={
                        "rule": self.name,
                        "decision": "VETO",
                        "reason": reason,
                        "symbol": symbol,
                    },
                )
                return PolicyEvaluation(
                    decision=PolicyDecision.VETO,
                    reason=reason,
                    rule_name=self.name,
                    signal_type=signal_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    metrics_snapshot=sym_stats,
                )
            
            return None
        except Exception as e:
            logger.error(f"Error evaluating symbol_drawdown rule: {e}", exc_info=True)
            return None


class OutcomePolicyEvaluator:
    """
    Deterministic policy evaluator consuming outcome stats.
    
    Applies static, configurable rules to determine if signals should be allowed or vetoed
    based on observed performance metrics. This is *policy feedback*, not learning.
    
    Key Properties:
    - Deterministic: Same inputs produce same outputs
    - Auditable: Every VETO is logged with structured reason
    - Non-Adaptive: No parameter tuning or feedback loops
    - Read-Only: Queries only, no writes
    - Composable: Rules can be added/removed dynamically
    
    Usage:
        evaluator = OutcomePolicyEvaluator(stats_service)
        evaluator.add_rule(WinRateThresholdRule(min_win_rate=0.50))
        evaluator.add_rule(LossStreakRule(max_streak=3))
        
        result = await evaluator.evaluate(
            signal_type="bullish_choch",
            symbol="EURUSD",
        )
        if result.decision == PolicyDecision.VETO:
            print(f"Signal vetoed: {result.reason}")
    """
    
    def __init__(self, stats_service: OutcomeStatsService):
        """
        Initialize evaluator.
        
        Args:
            stats_service: OutcomeStatsService instance for querying metrics
        """
        self.stats_service = stats_service
        self.rules: List[PolicyRule] = []
        self._evaluation_log: List[PolicyEvaluation] = []
    
    def add_rule(self, rule: PolicyRule) -> None:
        """
        Add a policy rule to the evaluator.
        
        Args:
            rule: PolicyRule instance to add
        """
        # Check for duplicate rule names
        if any(r.name == rule.name for r in self.rules):
            raise ValueError(f"Rule with name '{rule.name}' already exists")
        
        self.rules.append(rule)
        logger.debug(f"added_policy_rule", extra={"rule": rule.name})
    
    def remove_rule(self, rule_name: str) -> None:
        """
        Remove a policy rule by name.
        
        Args:
            rule_name: Name of the rule to remove
        """
        self.rules = [r for r in self.rules if r.name != rule_name]
        logger.debug(f"removed_policy_rule", extra={"rule": rule_name})
    
    def get_rules(self) -> List[PolicyRule]:
        """Get all active rules."""
        return self.rules.copy()
    
    async def evaluate(
        self,
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[PolicyEvaluation]:
        """
        Evaluate all rules and return first VETO (or None if all ALLOW).
        
        Deterministic: Rules are evaluated in order, first VETO wins.
        Auditable: All evaluations logged, first VETO returned with reason.
        
        Args:
            signal_type: Signal type to evaluate
            symbol: Symbol to evaluate
            timeframe: Timeframe to evaluate
        
        Returns:
            PolicyEvaluation with VETO if any rule fires, None if all ALLOW
        """
        try:
            for rule in self.rules:
                result = await rule.evaluate(
                    self.stats_service,
                    signal_type=signal_type,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                
                if result and result.decision == PolicyDecision.VETO:
                    # Log veto
                    self._evaluation_log.append(result)
                    logger.info(
                        f"policy_evaluation_veto",
                        extra={
                            "rule": result.rule_name,
                            "signal_type": result.signal_type,
                            "symbol": result.symbol,
                            "timeframe": result.timeframe,
                            "reason": result.reason,
                        },
                    )
                    # Return first veto
                    return result
            
            # All rules allowed (or no rules matched)
            logger.debug(
                f"policy_evaluation_allow",
                extra={
                    "signal_type": signal_type,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rule_count": len(self.rules),
                },
            )
            return None
        except Exception as e:
            logger.error(f"Error evaluating policies: {e}", exc_info=True)
            return None
    
    def get_evaluation_history(self, limit: int = 100) -> List[PolicyEvaluation]:
        """
        Get recent evaluations (for audit/monitoring).
        
        Args:
            limit: Maximum number of recent evaluations to return
        
        Returns:
            List of PolicyEvaluation records
        """
        return self._evaluation_log[-limit:]
    
    def clear_history(self) -> None:
        """Clear evaluation history (useful for testing)."""
        self._evaluation_log = []


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_policy_evaluator(
    stats_service: OutcomeStatsService,
    config: Optional[Dict[str, Any]] = None,
) -> OutcomePolicyEvaluator:
    """
    Factory function for creating OutcomePolicyEvaluator with default rules.
    
    Args:
        stats_service: OutcomeStatsService instance
        config: Optional configuration dict with keys:
            - win_rate_threshold: float (default: 0.45)
            - max_loss_streak: int (default: 5)
            - min_avg_pnl: float (default: 0.0)
            - symbol_max_drawdown: float (default: -500.0)
    
    Returns:
        OutcomePolicyEvaluator with default rules configured
    
    Example:
        config = {
            "win_rate_threshold": 0.50,
            "max_loss_streak": 3,
            "symbol_max_drawdown": -200.0,
        }
        evaluator = create_policy_evaluator(stats_service, config)
    """
    if config is None:
        config = {}
    
    evaluator = OutcomePolicyEvaluator(stats_service)
    
    # Add default rules with config overrides
    win_rate_rule = WinRateThresholdRule(
        min_win_rate=config.get("win_rate_threshold", 0.45),
        min_trades=config.get("min_win_rate_trades", 10),
    )
    evaluator.add_rule(win_rate_rule)
    
    loss_streak_rule = LossStreakRule(
        max_streak=config.get("max_loss_streak", 5),
    )
    evaluator.add_rule(loss_streak_rule)
    
    avg_pnl_rule = AvgPnLThresholdRule(
        min_avg_pnl=config.get("min_avg_pnl", 0.0),
        min_trades=config.get("min_avg_pnl_trades", 10),
    )
    evaluator.add_rule(avg_pnl_rule)
    
    drawdown_rule = SymbolDrawdownRule(
        max_drawdown=config.get("symbol_max_drawdown", -500.0),
        min_trades=config.get("min_drawdown_trades", 5),
    )
    evaluator.add_rule(drawdown_rule)
    
    logger.info(
        f"created_policy_evaluator",
        extra={
            "rule_count": len(evaluator.rules),
            "rules": [r.name for r in evaluator.rules],
        },
    )
    
    return evaluator
