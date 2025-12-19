from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Literal, List, Tuple, Any


@dataclass
class Event:
    """Event object for event-driven orchestration."""
    event_type: str
    payload: Dict
    timestamp: datetime
    correlation_id: str


@dataclass
class EventResult:
    """Result of event processing with advanced orchestration support."""
    status: Literal["accepted", "rejected", "deferred", "error", "escalated"]
    reason: Optional[str] = None
    decision_id: Optional[str] = None
    metadata: Dict = None
    
    # Advanced orchestration fields (backward compatible)
    event_state: Optional[str] = None  # pending, processed, deferred, escalated, discarded
    correlation_id: Optional[str] = None  # For event tracking
    processing_time_ms: Optional[int] = None  # Time to process
    policy_decisions: Optional[List[Dict[str, Any]]] = None  # Policy audit trail
    state_transitions: Optional[List[Tuple[str, int]]] = None  # State change history

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.policy_decisions is None:
            self.policy_decisions = []
        if self.state_transitions is None:
            self.state_transitions = []