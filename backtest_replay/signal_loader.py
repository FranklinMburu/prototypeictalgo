"""
Load historical signals from JSONL or database.

Supports:
- JSONL files with signal snapshots
- DecisionOutcome/Decision DB tables (async)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class ReplaySignal:
    """Signal record for replay testing."""
    signal_id: str
    timestamp: datetime  # Entry time, UTC-aware
    symbol: str
    timeframe: str
    direction: str  # "long" or "short"
    signal_type: str
    entry: float
    sl: float
    tp: float
    session: Optional[str] = None
    meta: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __lt__(self, other):
        """For sorting by timestamp."""
        return self.timestamp < other.timestamp


class SignalLoader:
    """Load historical signals from JSONL or DB."""

    @staticmethod
    def load_jsonl(
        jsonl_path: str,
        timestamp_fmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> List[ReplaySignal]:
        """
        Load signals from JSONL file.

        Expected JSONL format per line:
        {
            "signal_id": "...",
            "timestamp": "2024-01-01 10:30:00",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "direction": "long",
            "signal_type": "bearish_bos",
            "entry": 1.0850,
            "sl": 1.0820,
            "tp": 1.0900,
            "session": "london",
            "meta": {...}
        }

        Args:
            jsonl_path: Path to JSONL file
            timestamp_fmt: Timestamp format string

        Returns:
            List of ReplaySignal objects, sorted ascending by timestamp

        Raises:
            FileNotFoundError: If file not found
            ValueError: If lines malformed
        """
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"JSONL not found: {jsonl_path}")

        signals = []
        with open(path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)

                    # Parse timestamp
                    ts_str = data.get("timestamp", "")
                    ts = datetime.strptime(ts_str, timestamp_fmt)
                    if ts.tzinfo is None:
                        from datetime import timezone
                        ts = ts.replace(tzinfo=timezone.utc)

                    signal = ReplaySignal(
                        signal_id=str(data.get("signal_id", f"sig_{line_num}")),
                        timestamp=ts,
                        symbol=str(data.get("symbol", "")),
                        timeframe=str(data.get("timeframe", "")),
                        direction=str(data.get("direction", "")).lower(),
                        signal_type=str(data.get("signal_type", "")),
                        entry=float(data.get("entry", 0)),
                        sl=float(data.get("sl", 0)),
                        tp=float(data.get("tp", 0)),
                        session=data.get("session"),
                        meta=data.get("meta", {}),
                    )
                    signals.append(signal)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(
                        f"Error parsing JSONL line {line_num}: {e}\n"
                        f"Line: {line}"
                    )

        # Sort ascending by timestamp
        signals.sort()

        if not signals:
            raise ValueError("No valid signals loaded from JSONL")

        return signals

    @staticmethod
    async def load_from_db(
        sessionmaker,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[ReplaySignal]:
        """
        Load signals from DecisionOutcome/Decision DB tables.

        Args:
            sessionmaker: SQLAlchemy async sessionmaker
            symbol: Filter by symbol (optional)
            signal_type: Filter by signal type (optional)
            from_ts: Filter from timestamp (optional)
            to_ts: Filter to timestamp (optional)

        Returns:
            List of ReplaySignal objects, sorted ascending by timestamp
        """
        from reasoner_service.storage import Decision, DecisionOutcome

        signals = []
        async with sessionmaker() as session:
            # Build query
            query = session.select(Decision)

            if symbol:
                query = query.where(Decision.symbol == symbol)
            if signal_type:
                query = query.where(Decision.signal_type == signal_type)
            if from_ts:
                query = query.where(Decision.timestamp >= from_ts)
            if to_ts:
                query = query.where(Decision.timestamp <= to_ts)

            result = await session.execute(query)
            decisions = result.scalars().all()

            for decision in decisions:
                signal = ReplaySignal(
                    signal_id=str(decision.id),
                    timestamp=decision.timestamp,
                    symbol=decision.symbol,
                    timeframe=decision.timeframe,
                    direction=decision.direction,
                    signal_type=decision.signal_type,
                    entry=decision.entry_price,
                    sl=decision.sl_price,
                    tp=decision.tp_price,
                    session=decision.session,
                    meta={"decision_id": decision.id},
                )
                signals.append(signal)

        # Sort ascending by timestamp
        signals.sort()
        return signals
