"""
Outcome Analytics Service

A read-only analytics layer that aggregates historical outcomes and policy
evaluations to produce evidence for future enforcement decisions.

This service is PURELY ANALYTICAL:
- Zero side effects or state mutations
- Read-only access to DecisionOutcome table
- Deterministic outputs
- Designed to inform (not execute) enforcement decisions

Key Metrics:
1. Policy Veto Impact: Counterfactual analysis - what trades would have been
   blocked by policies, and how would they have performed?
2. Signal-Policy Heatmap: Breakdown of VETO rates by signal type, timeframe, session
3. Regime-Policy Performance: How policy effectiveness varies across market regimes

This service provides evidence for future enforcement decisions but NEVER
influences live trading execution.

FUTURE INTEGRATION POINTS:
- PolicyStore: Review analytics before enabling enforcement
- Dashboard: Visualize policy effectiveness before deployment
- A/B Testing: Compare policy versions side-by-side
- Backtesting: Simulate policy enforcement on historical data

NON-BREAKING DESIGN:
- Read-only queries (no side effects)
- Fail-silent error handling (analytics never crash execution)
- No modifications to DecisionOrchestrator or execution flow
- Deterministic outputs (same data → same results)
"""

import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.future import select
from sqlalchemy import func

from .storage import DecisionOutcome
from .outcome_stats import OutcomeStatsService

logger = logging.getLogger(__name__)


class OutcomeAnalyticsService:
    """
    Read-only analytics service for aggregating outcomes and evaluating
    policy effectiveness without influencing live trading.
    
    This service consumes:
    1. DecisionOutcome objects (historical trade results)
    2. OutcomePolicyEvaluation results (policy shadow mode evaluations)
    3. OutcomeStatsService queries (pre-computed metrics)
    
    Produces analytical evidence for future enforcement decisions:
    - Policy veto impact analysis (counterfactuals)
    - Signal-policy heatmaps (performance by dimensions)
    - Regime-based policy analysis (adaptive regime detection)
    
    CRITICAL: This service is PURELY ANALYTICAL and produces NO side effects.
    All outputs are designed for human review and future enforcement decisions,
    not for live trading.
    """
    
    def __init__(self, sessionmaker, stats_service: Optional[OutcomeStatsService] = None):
        """
        Initialize analytics service.
        
        Args:
            sessionmaker: Async SQLAlchemy sessionmaker for database access
            stats_service: Optional OutcomeStatsService for pre-computed metrics
        
        DESIGN NOTE:
        - Both parameters optional for testability
        - Database access kept to read-only queries
        - No state mutations beyond analytics
        """
        self.sessionmaker = sessionmaker
        self.stats_service = stats_service
        self._cache: Dict[str, Any] = {}
    
    async def get_outcomes_for_analysis(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        timeframe: Optional[str] = None,
        last_n_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve outcomes for analysis (read-only).
        
        Args:
            symbol: Filter by symbol
            signal_type: Filter by signal type
            timeframe: Filter by timeframe
            last_n_days: Limit to outcomes from last N days
        
        Returns:
            List of outcome dicts (empty list on error)
        
        FAIL-SILENT: Returns empty list on any error, logs exception
        """
        try:
            async with self.sessionmaker() as session:
                query = select(DecisionOutcome)
                
                if symbol:
                    query = query.where(DecisionOutcome.symbol == symbol)
                if signal_type:
                    query = query.where(DecisionOutcome.signal_type == signal_type)
                if timeframe:
                    query = query.where(DecisionOutcome.timeframe == timeframe)
                
                if last_n_days:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=last_n_days)
                    query = query.where(DecisionOutcome.closed_at >= cutoff)
                
                result = await session.execute(query.order_by(DecisionOutcome.closed_at))
                outcomes = result.scalars().all()
                
                return [
                    {
                        "id": o.id,
                        "symbol": o.symbol,
                        "signal_type": o.signal_type,
                        "timeframe": o.timeframe,
                        "pnl": o.pnl,
                        "outcome": o.outcome,  # "win", "loss", "breakeven"
                        "exit_reason": o.exit_reason,
                        "closed_at": o.closed_at,
                    }
                    for o in outcomes
                ]
        except Exception as e:
            logger.exception("Error retrieving outcomes for analysis: %s", e)
            return []
    
    def policy_veto_impact(
        self,
        outcomes: Optional[List[Dict[str, Any]]] = None,
        shadow_evaluations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Counterfactual analysis: What if policies had been enforced?
        
        Analyzes the impact of policy vetoes by examining which trades would
        have been blocked and how those trades performed.
        
        Args:
            outcomes: List of DecisionOutcome dicts (if None, retrieved from DB)
            shadow_evaluations: List of policy shadow mode evaluation results
        
        Returns:
            {
                "total_trades": int,
                "would_have_been_vetoed": int,
                "vetoed_winners": int,
                "vetoed_losers": int,
                "veto_precision": float,  # wins / (wins + losses) among vetoed
                "veto_recall": float,  # vetoed_losers / total_losers
                "veto_false_positives": int,  # trades that would have won but were vetoed
                "veto_false_negatives": int,  # losing trades that wouldn't have been vetoed
                "analysis_period": str,
                "note": str,
            }
        
        INTERPRETATION:
        - veto_precision: Of trades we would have vetoed, how many were actually losses?
          Higher precision = fewer false positives (fewer winners we'd block)
        - veto_recall: Of all losing trades, what percentage would we have caught?
          Higher recall = we'd catch more losers, but might be too conservative
        
        FUTURE USE:
        - PolicyStore: Review veto_precision before enabling enforcement
        - Dashboard: Visualize false positive rate (winners blocked)
        - Decision: Should we enforce this policy? What's the trade-off?
        """
        if outcomes is None:
            outcomes = []  # Would retrieve from DB in real usage
        
        if shadow_evaluations is None:
            shadow_evaluations = []
        
        # Build index: signal_type → shadow evaluation results
        veto_index = {}
        for eval_result in shadow_evaluations:
            if eval_result.get("decision") == "veto":
                key = (
                    eval_result.get("signal_type"),
                    eval_result.get("symbol"),
                    eval_result.get("timeframe"),
                )
                if key not in veto_index:
                    veto_index[key] = []
                veto_index[key].append(eval_result)
        
        # Analyze veto impact
        total_trades = len(outcomes)
        would_have_been_vetoed = 0
        vetoed_winners = 0
        vetoed_losers = 0
        
        for outcome in outcomes:
            key = (
                outcome.get("signal_type"),
                outcome.get("symbol"),
                outcome.get("timeframe"),
            )
            
            if key in veto_index:
                would_have_been_vetoed += 1
                
                if outcome.get("outcome") == "win":
                    vetoed_winners += 1
                elif outcome.get("outcome") == "loss":
                    vetoed_losers += 1
        
        # Calculate metrics
        total_losers = sum(1 for o in outcomes if o.get("outcome") == "loss")
        
        veto_precision = (
            vetoed_losers / would_have_been_vetoed
            if would_have_been_vetoed > 0
            else 0.0
        )
        
        veto_recall = (
            vetoed_losers / total_losers
            if total_losers > 0
            else 0.0
        )
        
        veto_false_positives = vetoed_winners
        veto_false_negatives = total_losers - vetoed_losers
        
        return {
            "total_trades": total_trades,
            "would_have_been_vetoed": would_have_been_vetoed,
            "vetoed_winners": vetoed_winners,
            "vetoed_losers": vetoed_losers,
            "veto_precision": round(veto_precision, 4),
            "veto_recall": round(veto_recall, 4),
            "veto_false_positives": veto_false_positives,
            "veto_false_negatives": veto_false_negatives,
            "analysis_period": datetime.now(timezone.utc).isoformat(),
            "note": "Counterfactual analysis: what if policies had been enforced? "
                    "This service does not influence decisions.",
        }
    
    def signal_policy_heatmap(
        self,
        outcomes: Optional[List[Dict[str, Any]]] = None,
        shadow_evaluations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Policy veto rates by signal type, timeframe, and session.
        
        Breakdown of how often each signal type would have been vetoed, and
        the performance characteristics of those vetoed trades.
        
        Args:
            outcomes: List of DecisionOutcome dicts
            shadow_evaluations: List of policy shadow mode evaluation results
        
        Returns:
            {
                "by_signal_type": {
                    "bullish_choch": {
                        "total_trades": int,
                        "vetoed_trades": int,
                        "veto_rate": float,
                        "performance_if_vetoed": {"wins": int, "losses": int},
                        "performance_if_allowed": {"wins": int, "losses": int},
                    },
                    ...
                },
                "by_timeframe": {
                    "4H": {...},
                    ...
                },
                "by_session": {
                    "london": {...},
                    ...
                },
                "analysis_period": str,
            }
        
        INTERPRETATION:
        - High veto_rate + high performance_if_allowed = policy too aggressive
        - Low veto_rate + high performance_if_vetoed = policy not aggressive enough
        - High veto_rate + high performance_if_vetoed = policy well-calibrated
        
        FUTURE USE:
        - Dashboard: Heatmap visualization
        - Decision: Which signal types need different policies?
        - Tuning: Parameter adjustment based on observed impact
        """
        if outcomes is None:
            outcomes = []
        if shadow_evaluations is None:
            shadow_evaluations = []
        
        # Build veto index - support both (signal, symbol, tf) and (signal, tf) keys
        veto_index = set()
        veto_index_by_signal_tf = set()
        for eval_result in shadow_evaluations:
            if eval_result.get("decision") == "veto":
                key = (
                    eval_result.get("signal_type"),
                    eval_result.get("symbol"),
                    eval_result.get("timeframe"),
                )
                veto_index.add(key)
                # Also index by signal + timeframe only for cases where symbol might be missing
                signal_tf_key = (
                    eval_result.get("signal_type"),
                    eval_result.get("timeframe"),
                )
                veto_index_by_signal_tf.add(signal_tf_key)
        
        # Aggregate by signal type
        by_signal_type = defaultdict(lambda: {
            "total_trades": 0,
            "vetoed_trades": 0,
            "performance_if_vetoed": {"wins": 0, "losses": 0, "breakeven": 0},
            "performance_if_allowed": {"wins": 0, "losses": 0, "breakeven": 0},
        })
        
        for outcome in outcomes:
            signal = outcome.get("signal_type", "unknown")
            key = (
                outcome.get("signal_type"),
                outcome.get("symbol"),
                outcome.get("timeframe"),
            )
            signal_tf_key = (
                outcome.get("signal_type"),
                outcome.get("timeframe"),
            )
            
            by_signal_type[signal]["total_trades"] += 1
            
            # Check both full key and signal+timeframe key
            is_vetoed = key in veto_index or (outcome.get("symbol") is None and signal_tf_key in veto_index_by_signal_tf)
            if is_vetoed:
                by_signal_type[signal]["vetoed_trades"] += 1
                perf_key = outcome.get("outcome", "breakeven")
                if perf_key not in by_signal_type[signal]["performance_if_vetoed"]:
                    by_signal_type[signal]["performance_if_vetoed"][perf_key] = 0
                by_signal_type[signal]["performance_if_vetoed"][perf_key] += 1
            else:
                perf_key = outcome.get("outcome", "breakeven")
                if perf_key not in by_signal_type[signal]["performance_if_allowed"]:
                    by_signal_type[signal]["performance_if_allowed"][perf_key] = 0
                by_signal_type[signal]["performance_if_allowed"][perf_key] += 1
        
        # Compute veto rates
        result_by_signal = {}
        for signal, stats in by_signal_type.items():
            veto_rate = (
                stats["vetoed_trades"] / stats["total_trades"]
                if stats["total_trades"] > 0
                else 0.0
            )
            result_by_signal[signal] = {
                "total_trades": stats["total_trades"],
                "vetoed_trades": stats["vetoed_trades"],
                "veto_rate": round(veto_rate, 4),
                "performance_if_vetoed": stats["performance_if_vetoed"],
                "performance_if_allowed": stats["performance_if_allowed"],
            }
        
        # Aggregate by timeframe (similar pattern)
        by_timeframe = defaultdict(lambda: {
            "total_trades": 0,
            "vetoed_trades": 0,
            "veto_rate": 0.0,
        })
        
        for outcome in outcomes:
            tf = outcome.get("timeframe", "unknown")
            key = (
                outcome.get("signal_type"),
                outcome.get("symbol"),
                outcome.get("timeframe"),
            )
            
            by_timeframe[tf]["total_trades"] += 1
            if key in veto_index:
                by_timeframe[tf]["vetoed_trades"] += 1
        
        for tf, stats in by_timeframe.items():
            stats["veto_rate"] = round(
                stats["vetoed_trades"] / stats["total_trades"]
                if stats["total_trades"] > 0
                else 0.0,
                4,
            )
        
        return {
            "by_signal_type": result_by_signal,
            "by_timeframe": dict(by_timeframe),
            "analysis_period": datetime.now(timezone.utc).isoformat(),
            "note": "Heatmap of policy veto rates by dimension. "
                    "This service does not influence decisions.",
        }
    
    def regime_policy_performance(
        self,
        outcomes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Policy performance across market regimes.
        
        Analyzes how policy effectiveness varies across different market
        conditions (trending, ranging, high volatility).
        
        Args:
            outcomes: List of DecisionOutcome dicts
        
        Returns:
            {
                "trending_market": {
                    "description": "High average PnL per trade",
                    "detection_threshold": float,
                    "trades_in_regime": int,
                    "win_rate": float,
                    "avg_pnl": float,
                },
                "ranging_market": {...},
                "high_volatility": {...},
                "analysis_period": str,
            }
        
        INTERPRETATION:
        - Policies may perform differently in different regimes
        - Trending markets: High PnL trades (good environment for policies)
        - Ranging markets: Lower PnL, more false signals (harder environment)
        - High volatility: Extreme outcomes, need different thresholds
        
        DETECTION STRATEGY:
        - Trending: High average PnL (> median + 1 std dev)
        - Ranging: Low average PnL (< median - 1 std dev)
        - High volatility: High PnL variance
        
        FUTURE USE:
        - PolicyStore: Adjust policy parameters by regime
        - Dashboard: Show regime-specific policy metrics
        - Decision: Should policies be different for each regime?
        """
        if outcomes is None:
            outcomes = []
        
        if not outcomes:
            return {
                "trending_market": {"trades_in_regime": 0},
                "ranging_market": {"trades_in_regime": 0},
                "high_volatility": {"trades_in_regime": 0},
                "analysis_period": datetime.now(timezone.utc).isoformat(),
                "note": "No outcomes available for regime analysis. "
                        "This service does not influence decisions.",
            }
        
        # Calculate overall statistics
        pnls = [o.get("pnl", 0) for o in outcomes]
        mean_pnl = sum(pnls) / len(pnls) if pnls else 0
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls) if pnls else 0
        std_dev = variance ** 0.5
        
        # Define regime thresholds
        trending_threshold = mean_pnl + std_dev
        ranging_threshold = mean_pnl - std_dev
        volatility_threshold = std_dev * 1.5
        
        # Categorize outcomes by regime
        regimes = {
            "trending_market": [],
            "ranging_market": [],
            "high_volatility": [],
        }
        
        for outcome in outcomes:
            pnl = outcome.get("pnl", 0)
            
            if abs(pnl) > volatility_threshold:
                regimes["high_volatility"].append(outcome)
            elif pnl > trending_threshold:
                regimes["trending_market"].append(outcome)
            elif pnl < ranging_threshold:
                regimes["ranging_market"].append(outcome)
        
        # Compute regime statistics
        result = {}
        for regime_name, regime_outcomes in regimes.items():
            if regime_outcomes:
                regime_pnls = [o.get("pnl", 0) for o in regime_outcomes]
                wins = sum(1 for o in regime_outcomes if o.get("outcome") == "win")
                losses = sum(1 for o in regime_outcomes if o.get("outcome") == "loss")
                
                win_rate = wins / len(regime_outcomes) if regime_outcomes else 0.0
                avg_pnl = sum(regime_pnls) / len(regime_pnls) if regime_pnls else 0.0
                
                result[regime_name] = {
                    "trades_in_regime": len(regime_outcomes),
                    "win_rate": round(win_rate, 4),
                    "loss_rate": round(losses / len(regime_outcomes), 4),
                    "avg_pnl": round(avg_pnl, 2),
                    "total_pnl": round(sum(regime_pnls), 2),
                }
            else:
                result[regime_name] = {
                    "trades_in_regime": 0,
                }
        
        result["analysis_period"] = datetime.now(timezone.utc).isoformat()
        result["note"] = "Market regime classification based on PnL statistics. " \
                         "This service does not influence decisions."
        
        return result
    
    async def full_analytics_report(
        self,
        last_n_days: Optional[int] = 30,
    ) -> Dict[str, Any]:
        """
        Comprehensive analytics report combining all analytics.
        
        Args:
            last_n_days: Analyze outcomes from the last N days (default 30)
        
        Returns:
            Complete analytics report with all metrics
        
        FAIL-SILENT: Returns partial report on any error
        """
        try:
            # Retrieve outcomes
            outcomes = await self.get_outcomes_for_analysis(last_n_days=last_n_days)
            
            # Mock shadow evaluations (in real usage, would query from audit trail)
            shadow_evaluations = []
            
            # Compute all analytics
            veto_impact = self.policy_veto_impact(outcomes, shadow_evaluations)
            heatmap = self.signal_policy_heatmap(outcomes, shadow_evaluations)
            regime_perf = self.regime_policy_performance(outcomes)
            
            return {
                "period_days": last_n_days,
                "total_outcomes_analyzed": len(outcomes),
                "policy_veto_impact": veto_impact,
                "signal_policy_heatmap": heatmap,
                "regime_policy_performance": regime_perf,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "This is analytical evidence for future enforcement decisions. "
                              "This service does NOT influence live trading.",
            }
        except Exception as e:
            logger.exception("Error generating full analytics report: %s", e)
            return {
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "This is analytical evidence for future enforcement decisions. "
                              "This service does NOT influence live trading.",
            }


async def create_analytics_service(
    sessionmaker,
    stats_service: Optional[OutcomeStatsService] = None,
) -> OutcomeAnalyticsService:
    """
    Factory function to create OutcomeAnalyticsService.
    
    Args:
        sessionmaker: Async SQLAlchemy sessionmaker
        stats_service: Optional OutcomeStatsService for enhanced analytics
    
    Returns:
        Initialized OutcomeAnalyticsService instance
    """
    return OutcomeAnalyticsService(sessionmaker, stats_service)
