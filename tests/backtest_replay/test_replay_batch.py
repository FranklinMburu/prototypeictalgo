"""
Tests for batch replay functionality.

Verifies:
- Correct grouping count and grouping logic
- Sorting logic (by expectancy desc, then sample_size desc)
- JSON file creation with proper structure
- Markdown file creation and content
- Deterministic output (same input → identical output)
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtest_replay.signal_loader import ReplaySignal
from backtest_replay.schemas import ReplayOutcome
from scripts.run_replay_batch import (
    GroupMetrics,
    compute_group_metrics,
    generate_json_report,
    generate_markdown_report,
    group_outcomes,
)


@pytest.fixture
def sample_signals():
    """Create sample signals for testing."""
    signals = [
        # EURUSD, 1h, london, bearish_bos, long
        ReplaySignal(
            signal_id="sig_001",
            timestamp=datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            symbol="EURUSD",
            timeframe="1h",
            direction="long",
            signal_type="bearish_bos",
            session="london",
            entry=1.0500,
            sl=1.0450,
            tp=1.0600,
            meta={},
        ),
        # EURUSD, 1h, london, bearish_bos, long
        ReplaySignal(
            signal_id="sig_002",
            timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            symbol="EURUSD",
            timeframe="1h",
            direction="long",
            signal_type="bearish_bos",
            session="london",
            entry=1.0510,
            sl=1.0460,
            tp=1.0610,
            meta={},
        ),
        # EURUSD, 1h, london, bullish_choch, short
        ReplaySignal(
            signal_id="sig_003",
            timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            symbol="EURUSD",
            timeframe="1h",
            direction="short",
            signal_type="bullish_choch",
            session="london",
            entry=1.0520,
            sl=1.0570,
            tp=1.0420,
            meta={},
        ),
        # GBPUSD, 4h, asia, bearish_bos, long
        ReplaySignal(
            signal_id="sig_004",
            timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            symbol="GBPUSD",
            timeframe="4h",
            direction="long",
            signal_type="bearish_bos",
            session="asia",
            entry=1.2700,
            sl=1.2650,
            tp=1.2800,
            meta={},
        ),
    ]
    return signals


@pytest.fixture
def sample_outcomes():
    """Create sample outcomes corresponding to signals."""
    outcomes = [
        # sig_001: WIN
        ReplayOutcome(
            signal_id="sig_001",
            outcome="WIN",
            r_multiple=2.0,
            mae=0.5,
            mfe=3.0,
            exit_price=1.0600,
            exit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
        # sig_002: LOSS
        ReplayOutcome(
            signal_id="sig_002",
            outcome="LOSS",
            r_multiple=-1.0,
            mae=1.5,
            mfe=0.0,
            exit_price=1.0460,
            exit_time=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        ),
        # sig_003: WIN
        ReplayOutcome(
            signal_id="sig_003",
            outcome="WIN",
            r_multiple=2.0,
            mae=0.5,
            mfe=2.0,
            exit_price=1.0420,
            exit_time=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
        ),
        # sig_004: LOSS
        ReplayOutcome(
            signal_id="sig_004",
            outcome="LOSS",
            r_multiple=-1.0,
            mae=2.0,
            mfe=0.0,
            exit_price=1.2650,
            exit_time=datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    return outcomes


class TestGrouping:
    """Test grouping logic."""

    def test_correct_group_count(self, sample_signals, sample_outcomes):
        """Verify correct number of groups created."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        # Expected groups:
        # 1. EURUSD|1h|London|bos|LONG (sig_001, sig_002)
        # 2. EURUSD|1h|London|choch|SHORT (sig_003)
        # 3. GBPUSD|4h|Asia|bos|LONG (sig_004)
        assert len(groups) == 3

    def test_group_keys(self, sample_signals, sample_outcomes):
        """Verify group keys are constructed correctly."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        expected_keys = {
            "EURUSD|1h|london|bearish_bos|long",
            "EURUSD|1h|london|bullish_choch|short",
            "GBPUSD|4h|asia|bearish_bos|long",
        }
        assert set(groups.keys()) == expected_keys

    def test_group_membership(self, sample_signals, sample_outcomes):
        """Verify signals are grouped correctly."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        # Group 1 should have sig_001 and sig_002
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        assert len(group1) == 2
        assert group1[0][0].signal_id == "sig_001"
        assert group1[1][0].signal_id == "sig_002"


class TestMetricsComputation:
    """Test per-group metrics computation."""

    def test_metrics_sample_size(self, sample_signals, sample_outcomes):
        """Verify sample_size is correct."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        assert metrics.sample_size == 2

    def test_metrics_completed_trades(self, sample_signals, sample_outcomes):
        """Verify completed_trades count."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        # sig_001: WIN, sig_002: LOSS → both completed
        assert metrics.completed_trades == 2

    def test_metrics_win_rate(self, sample_signals, sample_outcomes):
        """Verify win_rate is computed correctly."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        # 1 win out of 2 completed = 0.5
        assert metrics.win_rate == 0.5

    def test_metrics_expectancy(self, sample_signals, sample_outcomes):
        """Verify expectancy computation."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        # 1 win (2.0R), 1 loss (1.0R), win_rate=0.5
        # expectancy = (2.0 - 1.0) * 0.5 = 0.5R
        assert metrics.expectancy == 0.5

    def test_metrics_max_loss_streak(self, sample_signals, sample_outcomes):
        """Verify max_loss_streak computation."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        # Group 1: WIN, LOSS → max_loss_streak = 1
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        assert metrics.max_loss_streak == 1

    def test_metrics_max_drawdown(self, sample_signals, sample_outcomes):
        """Verify max_drawdown_r computation."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics = compute_group_metrics(group1[0][0], group1)
        # Cumulative: 2.0, then -1.0 → peak=2.0, current=1.0, dd=1.0
        assert metrics.max_drawdown_r == 1.0


class TestReportGeneration:
    """Test report generation."""

    def test_json_report_creation(self):
        """Verify JSON report is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="EURUSD",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=1.0,
                    max_loss_streak=2,
                    max_win_streak=3,
                )
            ]
            output_path = Path(tmpdir) / "summary.json"
            generate_json_report(metrics_list, output_path)
            assert output_path.exists()

    def test_json_report_structure(self):
        """Verify JSON report has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="EURUSD",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=1.0,
                    max_loss_streak=2,
                    max_win_streak=3,
                )
            ]
            output_path = Path(tmpdir) / "summary.json"
            generate_json_report(metrics_list, output_path)

            with open(output_path) as f:
                data = json.load(f)

            assert "timestamp" in data
            assert "total_groups" in data
            assert "groups" in data
            assert data["total_groups"] == 1
            assert len(data["groups"]) == 1
            assert data["groups"][0]["symbol"] == "EURUSD"
            assert data["groups"][0]["expectancy"] == 0.5

    def test_markdown_report_creation(self):
        """Verify Markdown report is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="EURUSD",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=1.0,
                    max_loss_streak=2,
                    max_win_streak=3,
                )
            ]
            output_path = Path(tmpdir) / "summary.md"
            generate_markdown_report(metrics_list, output_path)
            assert output_path.exists()

    def test_markdown_report_content(self):
        """Verify Markdown report contains expected content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="EURUSD",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=1.0,
                    max_loss_streak=2,
                    max_win_streak=3,
                )
            ]
            output_path = Path(tmpdir) / "summary.md"
            generate_markdown_report(metrics_list, output_path)

            content = output_path.read_text()
            assert "EURUSD" in content
            assert "1h" in content
            assert "London" in content
            assert "bos" in content
            assert "LONG" in content
            assert "0.5000R" in content or "0.5" in content

    def test_markdown_sorting(self):
        """Verify Markdown report is sorted by expectancy desc, then sample_size desc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="A",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=5,
                    completed_trades=5,
                    cancelled_trades=0,
                    win_rate=0.5,
                    loss_rate=0.5,
                    be_rate=0.0,
                    expectancy=1.0,
                    max_drawdown_r=1.0,
                    max_loss_streak=1,
                    max_win_streak=1,
                ),
                GroupMetrics(
                    symbol="B",
                    timeframe="1h",
                    session="London",
                    signal_type="choch",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=1.0,
                    max_drawdown_r=1.0,
                    max_loss_streak=1,
                    max_win_streak=2,
                ),
                GroupMetrics(
                    symbol="C",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="SHORT",
                    sample_size=3,
                    completed_trades=3,
                    cancelled_trades=0,
                    win_rate=0.33,
                    loss_rate=0.67,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=2.0,
                    max_loss_streak=2,
                    max_win_streak=1,
                ),
            ]
            output_path = Path(tmpdir) / "summary.md"
            generate_markdown_report(metrics_list, output_path)

            content = output_path.read_text()
            # A and B both have expectancy=1.0, so B (sample_size=10) should come first
            a_pos = content.find("| A |")
            b_pos = content.find("| B |")
            c_pos = content.find("| C |")
            assert b_pos < a_pos, "B should come before A (same expectancy, larger sample_size)"
            assert a_pos < c_pos, "A,B should come before C (higher expectancy)"


class TestDeterminism:
    """Test deterministic behavior."""

    def test_deterministic_grouping(self, sample_signals, sample_outcomes):
        """Verify same input produces same grouping."""
        groups1 = group_outcomes(sample_signals, sample_outcomes)
        groups2 = group_outcomes(sample_signals, sample_outcomes)
        assert groups1.keys() == groups2.keys()

    def test_deterministic_metrics(self, sample_signals, sample_outcomes):
        """Verify same input produces same metrics."""
        groups = group_outcomes(sample_signals, sample_outcomes)
        group1 = groups["EURUSD|1h|london|bearish_bos|long"]
        metrics1 = compute_group_metrics(group1[0][0], group1)
        metrics2 = compute_group_metrics(group1[0][0], group1)
        assert asdict(metrics1) == asdict(metrics2)

    def test_deterministic_json_report(self):
        """Verify JSON report is identical for same input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_list = [
                GroupMetrics(
                    symbol="EURUSD",
                    timeframe="1h",
                    session="London",
                    signal_type="bos",
                    direction="LONG",
                    sample_size=10,
                    completed_trades=10,
                    cancelled_trades=0,
                    win_rate=0.6,
                    loss_rate=0.4,
                    be_rate=0.0,
                    expectancy=0.5,
                    max_drawdown_r=1.0,
                    max_loss_streak=2,
                    max_win_streak=3,
                )
            ]
            output_path1 = Path(tmpdir) / "summary1.json"
            output_path2 = Path(tmpdir) / "summary2.json"

            generate_json_report(metrics_list, output_path1)
            generate_json_report(metrics_list, output_path2)

            # Compare content (ignoring timestamp)
            with open(output_path1) as f:
                data1 = json.load(f)
            with open(output_path2) as f:
                data2 = json.load(f)

            assert data1["groups"] == data2["groups"]
            assert data1["total_groups"] == data2["total_groups"]


def asdict(obj):
    """Convert dataclass to dict."""
    from dataclasses import asdict as dc_asdict
    return dc_asdict(obj)
