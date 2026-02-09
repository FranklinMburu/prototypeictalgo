"""Tests for metrics snapshot loader."""

import json

from reasoner_service.metrics_snapshot import load_metrics_snapshot


def test_load_metrics_snapshot_parses_keys(tmp_path) -> None:
    path = tmp_path / "snapshot.json"
    data = {
        "[\"ES\", \"MODEL\", \"London\"]": {"count": 25, "expectancy": 0.1, "win_rate": 0.6},
        "NQ,MODEL,NewYork": {"count": 30, "expectancy": -0.1, "win_rate": 0.4},
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    snapshot = load_metrics_snapshot(str(path))

    assert snapshot[("ES", "MODEL", "London")]["count"] == 25
    assert snapshot[("NQ", "MODEL", "NewYork")]["win_rate"] == 0.4


def test_load_metrics_snapshot_handles_errors(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")

    snapshot = load_metrics_snapshot(str(path))

    assert snapshot == {}
