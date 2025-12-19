"""
Outcome Statistics Service

Aggregates DecisionOutcome data and computes rolling metrics for observable
decision performance without introducing policy changes or learning logic.

This module provides read-only access to outcome analytics, enabling:
- PolicyStore to query performance trends (future integration)
- ReasoningManager to observe signal quality (future integration)
- Observability systems to track metrics (Prometheus, etc.)

The service follows async patterns consistent with storage.py and maintains
determinism and auditability throughout.

Key Features:
- Win rate computation (total, by signal type, by symbol, by timeframe)
- Average P&L analysis (per trade, aggregated)
- Loss streak tracking (consecutive losses, max streak)
- Flexible filtering (symbol, timeframe, signal_type, time windows)
- Rolling window metrics (last N trades, last N days)
- Non-blocking error handling (graceful degradation)

Future Integration Points:
1. PolicyStore: Query win_rate by signal_type to adjust entry/exit policies
2. ReasoningManager: Use loss_streak to suppress underperforming signal types
3. Observability: Export win_rate, avg_pnl, loss_streak as Prometheus metrics
4. EventTracker: Link outcome stats to market regime/volatility for learning
5. A/B Testing: Compare metrics across policy versions

Non-Breaking Design:
- Read-only queries (no side effects on DecisionOutcome table)
- No modifications to existing orchestration flow
- Deterministic outputs (same inputs → same metrics)
- Comprehensive logging for auditability
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from logging import getLogger
from collections import defaultdict, deque

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from .storage import DecisionOutcome

logger = getLogger(__name__)


class OutcomeStatsService:
    """
    Async service for computing outcome statistics and rolling metrics.
    
    Provides read-only aggregation of DecisionOutcome data, enabling
    observable decision performance analysis without policy changes.
    
    All queries are deterministic and support flexible filtering by:
    - symbol (e.g., "EURUSD")
    - timeframe (e.g., "4H")
    - signal_type (e.g., "bullish_choch")
    - time windows (e.g., last 24 hours, last 100 trades)
    
    Non-blocking: DB errors are caught, logged, and empty results returned.
    """

    def __init__(self, sessionmaker):
        """
        Initialize the OutcomeStatsService.
        
        Args:
            sessionmaker: Async SQLAlchemy sessionmaker bound to database
        """
        self.sessionmaker = sessionmaker
        self._cache: Dict[str, Any] = {}  # Simple cache for repeated queries
        self._cache_ttl_seconds = 60

    async def get_win_rate(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        signal_type: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> Optional[float]:
        """
        Compute win rate (fraction of trades that are wins).
        
        Win rate = (count of outcomes where outcome == "win") / (total count)
        
        Returns a value between 0.0 and 1.0, or None on error.
        
        FUTURE INTEGRATION POINT:
        - PolicyStore will use this to adjust entry/exit policies per signal type
        - PolicyGate will increase exposure for high win_rate signal types
        
        Args:
            symbol: Filter by symbol (e.g., "EURUSD")
            timeframe: Filter by timeframe (e.g., "4H")
            signal_type: Filter by signal type (e.g., "bullish_choch")
            last_n_trades: Only consider last N trades (ordering by closed_at DESC)
            last_n_days: Only consider trades closed in last N days
        
        Returns:
            float: Win rate between 0.0 and 1.0, or None on error
        
        Example:
            >>> service = OutcomeStatsService(sessionmaker)
            >>> wr = await service.get_win_rate(symbol="EURUSD", signal_type="bullish_choch")
            >>> print(f"EURUSD bullish_choch win rate: {wr:.2%}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                last_n_trades=last_n_trades,
                last_n_days=last_n_days,
            )
            if not outcomes:
                return None
            
            wins = sum(1 for o in outcomes if o["outcome"] == "win")
            total = len(outcomes)
            
            wr = wins / total if total > 0 else None
            logger.debug(
                f"computed_win_rate",
                extra={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": signal_type,
                    "wins": wins,
                    "total": total,
                    "win_rate": wr,
                },
            )
            return wr
        except Exception as e:
            logger.error(f"Error computing win rate: {e}", exc_info=True)
            return None

    async def get_avg_pnl(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        signal_type: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> Optional[float]:
        """
        Compute average P&L per trade.
        
        avg_pnl = sum(pnl) / count(trades)
        
        FUTURE INTEGRATION POINT:
        - PolicyStore will use this to assess expectancy of signal types
        - PolicyGate will prioritize high-expectancy signals in tight markets
        
        Args:
            symbol: Filter by symbol
            timeframe: Filter by timeframe
            signal_type: Filter by signal type
            last_n_trades: Only consider last N trades
            last_n_days: Only consider trades in last N days
        
        Returns:
            float: Average P&L, or None on error
        
        Example:
            >>> avg = await service.get_avg_pnl(symbol="EURUSD")
            >>> print(f"Average P&L: {avg:.2f}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                last_n_trades=last_n_trades,
                last_n_days=last_n_days,
            )
            if not outcomes:
                return None
            
            avg = sum(o["pnl"] for o in outcomes) / len(outcomes)
            logger.debug(
                f"computed_avg_pnl",
                extra={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": signal_type,
                    "avg_pnl": avg,
                    "count": len(outcomes),
                },
            )
            return avg
        except Exception as e:
            logger.error(f"Error computing average P&L: {e}", exc_info=True)
            return None

    async def get_loss_streak(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        signal_type: Optional[str] = None,
    ) -> Optional[Dict[str, int]]:
        """
        Compute current and maximum consecutive loss streaks.
        
        Returns dict with keys:
        - "current": Number of consecutive losses ending at most recent trade
        - "max": Maximum consecutive losses in history
        
        FUTURE INTEGRATION POINT:
        - ReasoningManager will suppress signal types with high loss streaks
        - EventTracker will correlate loss streaks with market regime changes
        
        Args:
            symbol: Filter by symbol
            timeframe: Filter by timeframe
            signal_type: Filter by signal type
        
        Returns:
            dict with "current" and "max" streaks, or None on error
        
        Example:
            >>> streaks = await service.get_loss_streak(signal_type="bearish_bos")
            >>> print(f"Current loss streak: {streaks['current']}, Max: {streaks['max']}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                last_n_trades=None,  # Get all history for streak analysis
                last_n_days=None,
            )
            if not outcomes:
                return None
            
            # Outcomes already sorted by closed_at DESC, reverse to chronological order
            outcomes = list(reversed(outcomes))
            
            current_streak = 0
            max_streak = 0
            
            for outcome in outcomes:
                if outcome["outcome"] == "loss":
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 0
            
            # Reverse the outcomes to get DESC order again, then compute current streak
            outcomes = list(reversed(outcomes))
            current_streak = 0
            for outcome in outcomes:
                if outcome["outcome"] == "loss":
                    current_streak += 1
                else:
                    break
            
            result = {"current": current_streak, "max": max_streak}
            logger.debug(
                f"computed_loss_streak",
                extra={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": signal_type,
                    "current": current_streak,
                    "max": max_streak,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error computing loss streak: {e}", exc_info=True)
            return None

    async def aggregate_by_signal_type(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Aggregate outcomes grouped by signal_type.
        
        Returns dict mapping signal_type → {
            "count": total trades,
            "wins": winning trades,
            "losses": losing trades,
            "breakevens": breakeven trades,
            "win_rate": fraction,
            "avg_pnl": average P&L,
            "total_pnl": sum of all P&L,
        }
        
        Returns None on error (non-blocking error handling).
        
        FUTURE INTEGRATION POINT:
        - PolicyStore will use this to enable/disable signal types
        - A/B Testing will compare signal quality across versions
        
        Example:
            >>> stats = await service.aggregate_by_signal_type(symbol="EURUSD")
            >>> for sig_type, metrics in stats.items():
            ...     print(f"{sig_type}: WR={metrics['win_rate']:.2%}, AvgPnL={metrics['avg_pnl']:.2f}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=None,
                last_n_trades=last_n_trades,
                last_n_days=last_n_days,
            )
            if not outcomes:
                return None
            
            stats: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {
                    "count": 0,
                    "wins": 0,
                    "losses": 0,
                    "breakevens": 0,
                    "total_pnl": 0.0,
                }
            )
            
            for outcome in outcomes:
                sig_type = outcome["signal_type"]
                stats[sig_type]["count"] += 1
                stats[sig_type]["total_pnl"] += outcome["pnl"]
                
                if outcome["outcome"] == "win":
                    stats[sig_type]["wins"] += 1
                elif outcome["outcome"] == "loss":
                    stats[sig_type]["losses"] += 1
                else:
                    stats[sig_type]["breakevens"] += 1
            
            # Add computed metrics
            for sig_type in stats:
                count = stats[sig_type]["count"]
                stats[sig_type]["win_rate"] = (
                    stats[sig_type]["wins"] / count if count > 0 else 0.0
                )
                stats[sig_type]["avg_pnl"] = (
                    stats[sig_type]["total_pnl"] / count if count > 0 else 0.0
                )
            
            logger.debug(
                f"aggregated_by_signal_type",
                extra={"signal_types": len(stats), "total_trades": sum(s["count"] for s in stats.values())},
            )
            return dict(stats)
        except Exception as e:
            logger.error(f"Error aggregating by signal type: {e}", exc_info=True)
            return None

    async def aggregate_by_symbol(
        self,
        timeframe: Optional[str] = None,
        signal_type: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Aggregate outcomes grouped by symbol.
        
        Returns dict mapping symbol → {
            "count": total trades,
            "wins": winning trades,
            "losses": losing trades,
            "breakevens": breakeven trades,
            "win_rate": fraction,
            "avg_pnl": average P&L,
            "total_pnl": sum of all P&L,
        }
        
        Returns None on error (non-blocking error handling).
        
        FUTURE INTEGRATION POINT:
        - PolicyStore will adjust symbol-specific exposure limits
        - Observability will track performance per trading pair
        
        Example:
            >>> stats = await service.aggregate_by_symbol()
            >>> for symbol, metrics in stats.items():
            ...     print(f"{symbol}: {metrics['count']} trades, WR={metrics['win_rate']:.2%}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=None,
                timeframe=timeframe,
                signal_type=signal_type,
                last_n_trades=last_n_trades,
                last_n_days=last_n_days,
            )
            if not outcomes:
                return None
            
            stats: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {
                    "count": 0,
                    "wins": 0,
                    "losses": 0,
                    "breakevens": 0,
                    "total_pnl": 0.0,
                }
            )
            
            for outcome in outcomes:
                symbol = outcome["symbol"]
                stats[symbol]["count"] += 1
                stats[symbol]["total_pnl"] += outcome["pnl"]
                
                if outcome["outcome"] == "win":
                    stats[symbol]["wins"] += 1
                elif outcome["outcome"] == "loss":
                    stats[symbol]["losses"] += 1
                else:
                    stats[symbol]["breakevens"] += 1
            
            # Add computed metrics
            for symbol in stats:
                count = stats[symbol]["count"]
                stats[symbol]["win_rate"] = (
                    stats[symbol]["wins"] / count if count > 0 else 0.0
                )
                stats[symbol]["avg_pnl"] = (
                    stats[symbol]["total_pnl"] / count if count > 0 else 0.0
                )
            
            logger.debug(
                f"aggregated_by_symbol",
                extra={"symbols": len(stats), "total_trades": sum(s["count"] for s in stats.values())},
            )
            return dict(stats)
        except Exception as e:
            logger.error(f"Error aggregating by symbol: {e}", exc_info=True)
            return None

    async def aggregate_by_timeframe(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Aggregate outcomes grouped by timeframe.
        
        Returns dict mapping timeframe → {
            "count": total trades,
            "wins": winning trades,
            "losses": losing trades,
            "breakevens": breakeven trades,
            "win_rate": fraction,
            "avg_pnl": average P&L,
            "total_pnl": sum of all P&L,
        }
        
        Returns None on error (non-blocking error handling).
        
        FUTURE INTEGRATION POINT:
        - PolicyStore will adjust timeframe-specific entry/exit thresholds
        - EventTracker will correlate performance with market structure
        
        Example:
            >>> stats = await service.aggregate_by_timeframe(symbol="EURUSD")
            >>> for tf, metrics in stats.items():
            ...     print(f"{tf}: {metrics['count']} trades, AvgPnL={metrics['avg_pnl']:.2f}")
        """
        try:
            outcomes = await self._get_filtered_outcomes(
                symbol=symbol,
                timeframe=None,
                signal_type=signal_type,
                last_n_trades=last_n_trades,
                last_n_days=last_n_days,
            )
            if not outcomes:
                return None
            
            stats: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {
                    "count": 0,
                    "wins": 0,
                    "losses": 0,
                    "breakevens": 0,
                    "total_pnl": 0.0,
                }
            )
            
            for outcome in outcomes:
                timeframe = outcome["timeframe"]
                stats[timeframe]["count"] += 1
                stats[timeframe]["total_pnl"] += outcome["pnl"]
                
                if outcome["outcome"] == "win":
                    stats[timeframe]["wins"] += 1
                elif outcome["outcome"] == "loss":
                    stats[timeframe]["losses"] += 1
                else:
                    stats[timeframe]["breakevens"] += 1
            
            # Add computed metrics
            for timeframe in stats:
                count = stats[timeframe]["count"]
                stats[timeframe]["win_rate"] = (
                    stats[timeframe]["wins"] / count if count > 0 else 0.0
                )
                stats[timeframe]["avg_pnl"] = (
                    stats[timeframe]["total_pnl"] / count if count > 0 else 0.0
                )
            
            logger.debug(
                f"aggregated_by_timeframe",
                extra={"timeframes": len(stats), "total_trades": sum(s["count"] for s in stats.values())},
            )
            return dict(stats)
        except Exception as e:
            logger.error(f"Error aggregating by timeframe: {e}", exc_info=True)
            return None

    async def get_session_metrics(
        self,
        session_start: Optional[datetime] = None,
        session_end: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get aggregated metrics for a trading session.
        
        A session is a time window (e.g., daily, weekly trading period).
        
        Returns dict with:
        {
            "session_start": session_start,
            "session_end": session_end,
            "count": total trades in session,
            "wins": winning trades,
            "losses": losing trades,
            "breakevens": breakeven trades,
            "win_rate": fraction,
            "avg_pnl": average P&L,
            "total_pnl": sum of all P&L,
            "max_loss": single worst trade,
            "max_win": single best trade,
        }
        
        FUTURE INTEGRATION POINT:
        - EventTracker will link sessions to market regimes/volatility
        - A/B Testing will compare sessions across policy versions
        
        Args:
            session_start: Start time (UTC). Defaults to 24 hours ago.
            session_end: End time (UTC). Defaults to now.
        
        Returns:
            dict with session metrics, or None on error
        
        Example:
            >>> metrics = await service.get_session_metrics()
            >>> print(f"Today: {metrics['count']} trades, WR={metrics['win_rate']:.2%}, Total PnL={metrics['total_pnl']:.2f}")
        """
        try:
            if session_start is None:
                session_start = datetime.now(timezone.utc) - timedelta(days=1)
            if session_end is None:
                session_end = datetime.now(timezone.utc)
            
            async with self.sessionmaker() as session:
                query = select(DecisionOutcome).where(
                    (DecisionOutcome.closed_at >= session_start)
                    & (DecisionOutcome.closed_at <= session_end)
                )
                result = await session.execute(query)
                outcomes_orm = result.scalars().all()
            
            if not outcomes_orm:
                return None
            
            # Convert ORM to dicts
            outcomes = [
                {c.name: getattr(o, c.name) for c in DecisionOutcome.__table__.columns}
                for o in outcomes_orm
            ]
            
            wins = sum(1 for o in outcomes if o["outcome"] == "win")
            losses = sum(1 for o in outcomes if o["outcome"] == "loss")
            breakevens = sum(1 for o in outcomes if o["outcome"] == "breakeven")
            pnls = [o["pnl"] for o in outcomes]
            
            result_dict = {
                "session_start": session_start,
                "session_end": session_end,
                "count": len(outcomes),
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "win_rate": wins / len(outcomes) if len(outcomes) > 0 else 0.0,
                "avg_pnl": sum(pnls) / len(outcomes) if len(outcomes) > 0 else 0.0,
                "total_pnl": sum(pnls),
                "max_loss": min(pnls) if pnls else None,
                "max_win": max(pnls) if pnls else None,
            }
            
            logger.debug(
                f"computed_session_metrics",
                extra={
                    "session_start": session_start,
                    "session_end": session_end,
                    "count": result_dict["count"],
                    "win_rate": result_dict["win_rate"],
                    "total_pnl": result_dict["total_pnl"],
                },
            )
            return result_dict
        except Exception as e:
            logger.error(f"Error computing session metrics: {e}", exc_info=True)
            return None

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    async def _get_filtered_outcomes(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        signal_type: Optional[str] = None,
        last_n_trades: Optional[int] = None,
        last_n_days: Optional[int] = None,
    ) -> List[dict]:
        """
        Get outcomes with flexible filtering.
        
        Internal helper for outcome retrieval with optional filtering by:
        - symbol, timeframe, signal_type (exact match filters)
        - last_n_trades (ordering by closed_at DESC)
        - last_n_days (time window filter)
        
        Returns empty list on error (non-blocking).
        """
        try:
            async with self.sessionmaker() as session:
                query = select(DecisionOutcome)
                
                # Apply exact-match filters
                if symbol:
                    query = query.where(DecisionOutcome.symbol == symbol)
                if timeframe:
                    query = query.where(DecisionOutcome.timeframe == timeframe)
                if signal_type:
                    query = query.where(DecisionOutcome.signal_type == signal_type)
                
                # Apply time window filter
                if last_n_days:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=last_n_days)
                    query = query.where(DecisionOutcome.closed_at >= cutoff)
                
                # Order by closed_at DESC and apply limit
                query = query.order_by(DecisionOutcome.closed_at.desc())
                if last_n_trades:
                    query = query.limit(last_n_trades)
                
                result = await session.execute(query)
                outcomes_orm = result.scalars().all()
            
            # Convert ORM objects to dicts
            return [
                {c.name: getattr(o, c.name) for c in DecisionOutcome.__table__.columns}
                for o in outcomes_orm
            ]
        except Exception as e:
            logger.error(
                f"Error retrieving filtered outcomes: {e}",
                extra={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": signal_type,
                    "last_n_trades": last_n_trades,
                    "last_n_days": last_n_days,
                },
                exc_info=True,
            )
            return []


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_stats_service(sessionmaker) -> OutcomeStatsService:
    """
    Factory function for creating an OutcomeStatsService instance.
    
    Usage:
        from reasoner_service.outcome_stats import create_stats_service
        service = create_stats_service(sessionmaker)
        win_rate = await service.get_win_rate(symbol="EURUSD")
    
    Args:
        sessionmaker: Async SQLAlchemy sessionmaker bound to database
    
    Returns:
        OutcomeStatsService instance
    """
    return OutcomeStatsService(sessionmaker)
