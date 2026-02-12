"""
Run historical replay pipeline and compute metrics.

Pipeline:
1. Load candles from CSV
2. Load signals from JSONL or DB
3. Tag outcomes against candles
4. Compute metrics: expectancy, win rate, max drawdown, loss streak
5. Generate report
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from backtest_replay.candle_loader import Candle, CandleLoader
from backtest_replay.outcome_tagger import OutcomeTagger, TaggedOutcome
from backtest_replay.signal_loader import ReplaySignal, SignalLoader


@dataclass
class ReplayMetrics:
    """Computed replay metrics."""
    sample_size: int
    completed_trades: int
    cancelled_trades: int
    win_count: int
    loss_count: int
    be_count: int
    win_rate: float
    loss_rate: float
    be_rate: float
    expectancy: float
    profit_factor: float
    max_r: float
    min_r: float
    average_r: float
    max_drawdown_r: float
    max_loss_streak: int
    max_win_streak: int
    average_mae: float
    average_mfe: float
    r_distribution: Dict[str, int]
    grouped_by_session: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ReplayRunner:
    """Run replay pipeline and compute metrics."""

    @staticmethod
    def run(
        candles_csv: str,
        signals_jsonl: str,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> tuple[ReplayMetrics, List[TaggedOutcome]]:
        """
        Run full replay pipeline.

        Args:
            candles_csv: Path to candles CSV
            signals_jsonl: Path to signals JSONL
            symbol: Filter by symbol (optional)
            signal_type: Filter by signal type (optional)
            from_date: Filter from date (optional)
            to_date: Filter to date (optional)

        Returns:
            (metrics, outcomes)
        """
        # Load candles
        candles = CandleLoader.load_csv(candles_csv)

        # Load signals
        signals = SignalLoader.load_jsonl(signals_jsonl)

        # Filter by params
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        if from_date:
            signals = [s for s in signals if s.timestamp >= from_date]
        if to_date:
            signals = [s for s in signals if s.timestamp <= to_date]

        if not signals:
            raise ValueError("No signals match filter criteria")

        # Tag outcomes
        outcomes = OutcomeTagger.tag_from_candles(signals, candles)

        # Compute metrics
        metrics = ReplayRunner._compute_metrics(outcomes)

        return metrics, outcomes

    @staticmethod
    def _compute_metrics(outcomes: List[TaggedOutcome]) -> ReplayMetrics:
        """Compute metrics from outcomes."""
        sample_size = len(outcomes)
        completed_trades = sum(1 for o in outcomes if o.exit_type in ("tp", "sl"))
        cancelled_trades = sum(1 for o in outcomes if o.exit_type == "cancelled")

        # Count wins, losses, breakevens
        wins = [o for o in outcomes if o.r_multiple and o.r_multiple > 0]
        losses = [o for o in outcomes if o.r_multiple and o.r_multiple < 0]
        bes = [o for o in outcomes if o.r_multiple and o.r_multiple == 0]

        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(bes)

        # Rates
        win_rate = win_count / completed_trades if completed_trades > 0 else 0
        loss_rate = loss_count / completed_trades if completed_trades > 0 else 0
        be_rate = be_count / completed_trades if completed_trades > 0 else 0

        # Expectancy
        expectancy = (
            sum(o.r_multiple for o in wins) / win_count
            - sum(abs(o.r_multiple) for o in losses) / loss_count
        ) * win_rate if (win_count > 0 and loss_count > 0) else 0

        # Profit factor
        profit = sum(o.r_multiple for o in wins) if wins else 0
        loss_amt = sum(abs(o.r_multiple) for o in losses) if losses else 0
        profit_factor = profit / loss_amt if loss_amt > 0 else 0

        # R distribution
        r_values = [o.r_multiple for o in outcomes if o.r_multiple is not None]
        max_r = max(r_values) if r_values else 0
        min_r = min(r_values) if r_values else 0
        average_r = sum(r_values) / len(r_values) if r_values else 0

        # R distribution buckets
        r_dist = ReplayRunner._bucket_r_values(r_values)

        # Drawdown and streaks
        max_dd, max_loss_streak, max_win_streak = ReplayRunner._compute_drawdown_streaks(
            outcomes
        )

        # MAE/MFE
        mae_values = [o.mae for o in outcomes if o.mae is not None]
        mfe_values = [o.mfe for o in outcomes if o.mfe is not None]
        average_mae = sum(mae_values) / len(mae_values) if mae_values else 0
        average_mfe = sum(mfe_values) / len(mfe_values) if mfe_values else 0

        # Group by session
        grouped = ReplayRunner._group_by_session(outcomes)

        metrics = ReplayMetrics(
            sample_size=sample_size,
            completed_trades=completed_trades,
            cancelled_trades=cancelled_trades,
            win_count=win_count,
            loss_count=loss_count,
            be_count=be_count,
            win_rate=round(win_rate, 4),
            loss_rate=round(loss_rate, 4),
            be_rate=round(be_rate, 4),
            expectancy=round(expectancy, 4),
            profit_factor=round(profit_factor, 4),
            max_r=round(max_r, 4),
            min_r=round(min_r, 4),
            average_r=round(average_r, 4),
            max_drawdown_r=round(max_dd, 4),
            max_loss_streak=max_loss_streak,
            max_win_streak=max_win_streak,
            average_mae=round(average_mae, 4),
            average_mfe=round(average_mfe, 4),
            r_distribution=r_dist,
            grouped_by_session=grouped,
        )

        return metrics

    @staticmethod
    def _bucket_r_values(r_values: List[float]) -> Dict[str, int]:
        """Bucket r_values into ranges."""
        buckets = {
            "loss_gt_2r": 0,
            "loss_1r_to_2r": 0,
            "loss_0r_to_1r": 0,
            "breakeven": 0,
            "win_0r_to_1r": 0,
            "win_1r_to_2r": 0,
            "win_gt_2r": 0,
        }

        for r in r_values:
            if r < -2:
                buckets["loss_gt_2r"] += 1
            elif -2 <= r < -1:
                buckets["loss_1r_to_2r"] += 1
            elif -1 <= r < 0:
                buckets["loss_0r_to_1r"] += 1
            elif r == 0:
                buckets["breakeven"] += 1
            elif 0 < r <= 1:
                buckets["win_0r_to_1r"] += 1
            elif 1 < r <= 2:
                buckets["win_1r_to_2r"] += 1
            else:
                buckets["win_gt_2r"] += 1

        return buckets

    @staticmethod
    def _compute_drawdown_streaks(
        outcomes: List[TaggedOutcome],
    ) -> tuple[float, int, int]:
        """Compute max drawdown in R, max loss streak, max win streak."""
        r_values = [
            o.r_multiple for o in outcomes if o.r_multiple is not None
        ]
        if not r_values:
            return 0.0, 0, 0

        # Equity curve
        equity = 0.0
        peak_equity = 0.0
        max_dd = 0.0

        for r in r_values:
            equity += r
            if equity > peak_equity:
                peak_equity = equity
            dd = peak_equity - equity
            max_dd = max(max_dd, dd)

        # Loss and win streaks
        max_loss_streak = 0
        max_win_streak = 0
        current_loss_streak = 0
        current_win_streak = 0

        for r in r_values:
            if r < 0:
                current_loss_streak += 1
                max_loss_streak = max(max_loss_streak, current_loss_streak)
                current_win_streak = 0
            elif r > 0:
                current_win_streak += 1
                max_win_streak = max(max_win_streak, current_win_streak)
                current_loss_streak = 0
            else:
                current_loss_streak = 0
                current_win_streak = 0

        return max_dd, max_loss_streak, max_win_streak

    @staticmethod
    def _group_by_session(outcomes: List[TaggedOutcome]) -> Dict[str, Dict[str, Any]]:
        """Group metrics by session."""
        grouped = {}

        for outcome in outcomes:
            session = outcome.session or "unknown"
            if session not in grouped:
                grouped[session] = {
                    "count": 0,
                    "wins": 0,
                    "losses": 0,
                    "be": 0,
                    "win_rate": 0.0,
                    "expectancy": 0.0,
                    "r_values": [],
                }

            grouped[session]["count"] += 1
            if outcome.r_multiple is not None:
                grouped[session]["r_values"].append(outcome.r_multiple)

                if outcome.r_multiple > 0:
                    grouped[session]["wins"] += 1
                elif outcome.r_multiple < 0:
                    grouped[session]["losses"] += 1
                else:
                    grouped[session]["be"] += 1

        # Compute session metrics
        for session, data in grouped.items():
            r_vals = data.pop("r_values", [])
            total_completed = data["wins"] + data["losses"]
            if total_completed > 0:
                data["win_rate"] = round(data["wins"] / total_completed, 4)

            if data["wins"] > 0 and data["losses"] > 0:
                data["expectancy"] = round(
                    (sum(r for r in r_vals if r > 0) / data["wins"])
                    * (data["wins"] / len(r_vals))
                    - (sum(abs(r) for r in r_vals if r < 0) / data["losses"])
                    * (data["losses"] / len(r_vals)),
                    4,
                )

        return grouped
