"""
Backtest replay package initialization.

Provides utility classes and functions for replaying historical trading
signals, tagging outcomes and computing performance metrics. This
package is self-contained and has no dependencies on the live
execution pipeline.
"""

from .schemas import ReplaySignal, ReplayOutcome, Outcome

__all__ = ["ReplaySignal", "ReplayOutcome", "Outcome"]
