"""
Regression snapshot test for `DecisionOrchestrator` behavior.

Purpose:
- This test locks a golden snapshot that the orchestrator accepts today and ensures
  future changes to `DecisionOrchestrator` behavior are caught by CI.
- It is intentionally conservative: it does not call `DecisionOrchestrator.setup()`
  (which would initialize networked notifiers) and avoids persistence to keep the
  execution deterministic and isolated.

This file acts as a tripwire protecting orchestration authority: any change that
modifies how a snapshot is turned into a decision or how the orchestrator
processes that decision should cause this test to fail.
"""

import json
import os
import pytest

from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.reasoner import reason_from_snapshot

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "snapshot_golden.json")


@pytest.mark.asyncio
async def test_orchestrator_snapshot_regression():
    # Load the golden snapshot that represents a realistic incoming signal
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    # Produce a decision using the repository's reasoner (deterministic fallback)
    decision = await reason_from_snapshot(snapshot)

    # Sanity: the reasoner should produce a non-trivial decision for this snapshot
    # (confidence is on a 0-100 scale in the fallback implementation).
    assert isinstance(decision, dict)
    assert decision.get("symbol", "").upper() == snapshot.get("symbol", "").upper()
    assert "recommendation" in decision
    assert "confidence" in decision

    # Expect the fallback rule to recommend an "enter" when confidence > 80
    assert decision["recommendation"] == "enter"
    assert float(decision["confidence"]) == pytest.approx(90.0)

    # Instantiate orchestrator but do not call setup() to avoid external effects
    orch = DecisionOrchestrator()

    # Run one processing cycle in-memory (skip persistence for determinism)
    result = await orch.process_decision(decision, persist=False)

    # The orchestrator should return notify_results for routing channels.
    assert isinstance(result, dict)
    assert "notify_results" in result
    notify_results = result["notify_results"]
    assert isinstance(notify_results, dict)

    # Because we didn't initialize notifiers, notifications should be marked skipped/unconfigured
    for ch, r in notify_results.items():
        assert isinstance(r, dict)
        # Either notifier is unconfigured or notifications are intentionally skipped
        assert r.get("skipped") is True or r.get("ok") is False

    # No persistence failures for this flow (we didn't persist), DLQ should remain empty
    assert hasattr(orch, "_persist_dlq")
    assert len(orch._persist_dlq) == 0

    # No unexpected side-effects: engine/sessionmaker not created
    assert orch.engine is None or orch._sessionmaker is None
