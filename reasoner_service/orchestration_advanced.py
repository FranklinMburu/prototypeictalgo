"""
Advanced Event-Driven Orchestration for DecisionOrchestrator.

This module provides:
- Event correlation and state tracking
- Per-event-type cooldowns and session windows
- Advanced policy enforcement with advisory signal filtering
- Metrics and telemetry for reasoning and orchestration
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple
)


# ============================================================================
# EVENT STATE MANAGEMENT
# ============================================================================

class EventState(str, Enum):
    """Lifecycle states for tracked events."""
    PENDING = "pending"
    DEFERRED = "deferred"
    ESCALATED = "escalated"
    PROCESSED = "processed"
    DISCARDED = "discarded"


@dataclass
class EventTracker:
    """Tracks a single event's lifecycle and state."""
    correlation_id: str
    event_type: str
    state: EventState = EventState.PENDING
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    processed_at_ms: Optional[int] = None
    status_history: List[Tuple[EventState, int]] = field(default_factory=list)
    reason: Optional[str] = None
    decision_id: Optional[str] = None
    signals_count: int = 0
    errors: List[str] = field(default_factory=list)
    policy_decisions: Dict[str, str] = field(default_factory=dict)
    
    def update_state(self, new_state: EventState, reason: Optional[str] = None) -> None:
        """Atomically update event state with history."""
        self.state = new_state
        self.reason = reason
        self.status_history.append((new_state, int(time.time() * 1000)))
    
    def mark_processed(self, decision_id: str, signals_count: int = 0) -> None:
        """Mark event as processed with decision info."""
        self.decision_id = decision_id
        self.signals_count = signals_count
        self.processed_at_ms = int(time.time() * 1000)
        self.update_state(EventState.PROCESSED)
    
    def get_processing_time_ms(self) -> int:
        """Get time from creation to processing."""
        if self.processed_at_ms:
            return self.processed_at_ms - self.created_at_ms
        return int(time.time() * 1000) - self.created_at_ms


# ============================================================================
# COOLDOWN AND SESSION WINDOW MANAGEMENT
# ============================================================================

@dataclass
class CooldownConfig:
    """Configuration for per-event-type cooldowns."""
    event_type: str
    cooldown_ms: int  # Duration of cooldown after event
    max_events_per_window: Optional[int] = None  # Max events in cooldown window


@dataclass
class SessionWindow:
    """Defines session constraints for event processing."""
    event_type: str
    start_hour: int = 0  # 0-23 UTC
    end_hour: int = 23
    max_events: int = 100
    
    def is_active(self) -> bool:
        """Check if current time is within session window."""
        import time as time_module
        current_hour = time_module.gmtime(time.time()).tm_hour
        if self.start_hour <= self.end_hour:
            return self.start_hour <= current_hour <= self.end_hour
        else:  # Window wraps midnight
            return current_hour >= self.start_hour or current_hour <= self.end_hour


@dataclass
class CooldownTracker:
    """Tracks cooldown state for an event type."""
    event_type: str
    cooldown_until_ms: int = 0
    events_in_window: int = 0
    last_event_time_ms: int = 0
    
    def is_cooling_down(self) -> bool:
        """Check if currently in cooldown period."""
        return int(time.time() * 1000) < self.cooldown_until_ms
    
    def reset_window(self, cooldown_config: CooldownConfig) -> None:
        """Start new cooldown window."""
        now_ms = int(time.time() * 1000)
        self.cooldown_until_ms = now_ms + cooldown_config.cooldown_ms
        self.events_in_window = 0
        self.last_event_time_ms = now_ms


# ============================================================================
# METRICS AND TELEMETRY
# ============================================================================

@dataclass
class ReasoningMetrics:
    """Metrics for reasoning operations."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    total_execution_time_ms: int = 0
    total_signals_generated: int = 0
    
    def add_call(self, success: bool, execution_time_ms: int, signals: int = 0) -> None:
        """Record a reasoning call."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_execution_time_ms += execution_time_ms
        self.total_signals_generated += signals
    
    def get_average_execution_time_ms(self) -> float:
        """Get average execution time."""
        if self.total_calls == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_calls
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100


@dataclass
class OrchestrationMetrics:
    """Metrics for orchestration operations."""
    total_events: int = 0
    accepted_events: int = 0
    rejected_events: int = 0
    deferred_events: int = 0
    escalated_events: int = 0
    total_processing_time_ms: int = 0
    policy_vetoes: int = 0
    policy_defers: int = 0
    
    def add_event(self, status: str, processing_time_ms: int = 0) -> None:
        """Record an event processing."""
        self.total_events += 1
        if status == "accepted":
            self.accepted_events += 1
        elif status == "rejected":
            self.rejected_events += 1
        elif status == "deferred":
            self.deferred_events += 1
        elif status == "escalated":
            self.escalated_events += 1
        self.total_processing_time_ms += processing_time_ms
    
    def get_acceptance_rate(self) -> float:
        """Get acceptance rate as percentage."""
        if self.total_events == 0:
            return 0.0
        return (self.accepted_events / self.total_events) * 100


# ============================================================================
# POLICY DECISION RECORD
# ============================================================================

@dataclass
class PolicyDecision:
    """Record of a policy decision on an event."""
    policy_name: str
    decision: str  # "pass", "veto", "defer", "filtered"
    reason: Optional[str] = None
    signals_filtered: int = 0
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))


# ============================================================================
# SIGNAL FILTERING ENGINE
# ============================================================================

class SignalFilter:
    """Filters advisory signals based on policies."""
    
    def __init__(self, policy_store: Optional[Any] = None):
        """Initialize signal filter with optional policy store."""
        self.policy_store = policy_store
    
    async def apply_policies(
        self,
        signals: List[Any],
        event_type: str,
        context: Dict[str, Any]
    ) -> Tuple[List[Any], List[PolicyDecision]]:
        """
        Apply policies to advisory signals.
        
        Returns:
            Tuple of (filtered_signals, policy_decisions)
        """
        if not self.policy_store:
            return signals, []
        
        filtered_signals = []
        decisions: List[PolicyDecision] = []
        
        try:
            # Get signal filtering policy
            signal_policy = await self.policy_store.get_policy(
                f"signal_filter_{event_type}",
                context
            )
            
            if not signal_policy:
                return signals, []
            
            allow_high_confidence = signal_policy.get("allow_high_confidence", True)
            min_confidence = signal_policy.get("min_confidence", 0.0)
            blocked_signal_types = set(signal_policy.get("blocked_types", []))
            
            filtered_count = 0
            for signal in signals:
                confidence = signal.get("confidence")
                signal_type = signal.get("signal_type")
                
                # Apply filtering rules
                if signal_type in blocked_signal_types:
                    filtered_count += 1
                    continue
                
                if confidence is not None and confidence < min_confidence:
                    filtered_count += 1
                    continue
                
                filtered_signals.append(signal)
            
            if filtered_count > 0:
                decisions.append(
                    PolicyDecision(
                        policy_name=f"signal_filter_{event_type}",
                        decision="filtered",
                        signals_filtered=filtered_count
                    )
                )
        
        except Exception:
            # On policy error, return all signals
            filtered_signals = signals
        
        return filtered_signals, decisions


# ============================================================================
# EVENT CORRELATION MANAGER
# ============================================================================

class EventCorrelationManager:
    """Manages event correlation and state tracking."""
    
    def __init__(self, max_tracked_events: int = 10000):
        """Initialize correlation manager."""
        self.max_tracked_events = max_tracked_events
        self._events: Dict[str, EventTracker] = {}
        self._lock = asyncio.Lock()
    
    async def create_event_tracker(
        self,
        correlation_id: str,
        event_type: str
    ) -> EventTracker:
        """Create a new event tracker."""
        async with self._lock:
            # Cleanup old events if needed
            if len(self._events) >= self.max_tracked_events:
                # Remove oldest 10% of events
                to_remove = int(self.max_tracked_events * 0.1)
                sorted_events = sorted(
                    self._events.items(),
                    key=lambda x: x[1].created_at_ms
                )
                for cid, _ in sorted_events[:to_remove]:
                    del self._events[cid]
            
            tracker = EventTracker(correlation_id, event_type)
            self._events[correlation_id] = tracker
            return tracker
    
    async def get_event_tracker(self, correlation_id: str) -> Optional[EventTracker]:
        """Retrieve event tracker by correlation ID."""
        async with self._lock:
            return self._events.get(correlation_id)
    
    async def update_event_state(
        self,
        correlation_id: str,
        new_state: EventState,
        reason: Optional[str] = None
    ) -> bool:
        """Atomically update event state."""
        async with self._lock:
            tracker = self._events.get(correlation_id)
            if tracker:
                tracker.update_state(new_state, reason)
                return True
            return False
    
    async def get_event_history(
        self,
        correlation_id: str
    ) -> Optional[List[Tuple[EventState, int]]]:
        """Get event state history."""
        async with self._lock:
            tracker = self._events.get(correlation_id)
            if tracker:
                return tracker.status_history
            return None
    
    async def get_events_by_type(self, event_type: str) -> List[EventTracker]:
        """Get all events of a specific type."""
        async with self._lock:
            return [
                t for t in self._events.values()
                if t.event_type == event_type
            ]
    
    async def get_recent_events(
        self,
        event_type: str,
        since_ms: int
    ) -> List[EventTracker]:
        """Get recent events of a type."""
        async with self._lock:
            return [
                t for t in self._events.values()
                if t.event_type == event_type and t.created_at_ms >= since_ms
            ]


# ============================================================================
# COOLDOWN MANAGER
# ============================================================================

class CooldownManager:
    """Manages cooldowns and session windows for event types."""
    
    def __init__(self):
        """Initialize cooldown manager."""
        self._cooldowns: Dict[str, CooldownTracker] = {}
        self._cooldown_configs: Dict[str, CooldownConfig] = {}
        self._session_windows: Dict[str, SessionWindow] = {}
        self._lock = asyncio.Lock()
    
    async def configure_cooldown(self, config: CooldownConfig) -> None:
        """Configure cooldown for event type."""
        async with self._lock:
            self._cooldown_configs[config.event_type] = config
            if config.event_type not in self._cooldowns:
                self._cooldowns[config.event_type] = CooldownTracker(config.event_type)
    
    async def configure_session_window(self, window: SessionWindow) -> None:
        """Configure session window for event type."""
        async with self._lock:
            self._session_windows[window.event_type] = window
    
    async def check_cooldown(self, event_type: str) -> Tuple[bool, Optional[int]]:
        """
        Check if event type is in cooldown.
        
        Returns:
            Tuple of (is_cooling_down, next_available_ms)
        """
        async with self._lock:
            tracker = self._cooldowns.get(event_type)
            if not tracker:
                return False, None
            
            if tracker.is_cooling_down():
                return True, tracker.cooldown_until_ms
            return False, None
    
    async def check_session_window(self, event_type: str) -> bool:
        """Check if event type is within session window."""
        async with self._lock:
            window = self._session_windows.get(event_type)
            if not window:
                return True  # No constraint = allowed
            return window.is_active()
    
    async def check_event_limit(self, event_type: str) -> bool:
        """Check if event type has exceeded limit in window."""
        async with self._lock:
            window = self._session_windows.get(event_type)
            tracker = self._cooldowns.get(event_type)
            
            if not window or not tracker:
                return True  # No constraint = allowed
            
            return tracker.events_in_window < window.max_events
    
    async def record_event(self, event_type: str) -> None:
        """Record event for cooldown tracking."""
        async with self._lock:
            config = self._cooldown_configs.get(event_type)
            tracker = self._cooldowns.get(event_type)
            
            if config and tracker:
                tracker.events_in_window += 1
                tracker.last_event_time_ms = int(time.time() * 1000)
                
                # Reset window if cooldown expired
                if not tracker.is_cooling_down():
                    tracker.reset_window(config)


# ============================================================================
# ORCHESTRATION STATE MANAGER
# ============================================================================

class OrchestrationStateManager:
    """Manages overall orchestration state atomically."""
    
    def __init__(self):
        """Initialize state manager."""
        self.event_correlation = EventCorrelationManager()
        self.cooldown_manager = CooldownManager()
        self.reasoning_metrics = ReasoningMetrics()
        self.orchestration_metrics = OrchestrationMetrics()
        self._lock = asyncio.Lock()
    
    async def record_reasoning_call(
        self,
        success: bool,
        execution_time_ms: int,
        signals: int = 0
    ) -> None:
        """Record reasoning call metrics."""
        async with self._lock:
            self.reasoning_metrics.add_call(success, execution_time_ms, signals)
    
    async def record_event_processing(
        self,
        status: str,
        processing_time_ms: int = 0
    ) -> None:
        """Record event processing metrics."""
        async with self._lock:
            self.orchestration_metrics.add_event(status, processing_time_ms)
    
    async def get_reasoning_stats(self) -> Dict[str, Any]:
        """Get reasoning metrics snapshot."""
        async with self._lock:
            return {
                "total_calls": self.reasoning_metrics.total_calls,
                "successful_calls": self.reasoning_metrics.successful_calls,
                "failed_calls": self.reasoning_metrics.failed_calls,
                "timeout_calls": self.reasoning_metrics.timeout_calls,
                "success_rate": self.reasoning_metrics.get_success_rate(),
                "avg_execution_time_ms": self.reasoning_metrics.get_average_execution_time_ms(),
                "total_signals": self.reasoning_metrics.total_signals_generated
            }
    
    async def get_orchestration_stats(self) -> Dict[str, Any]:
        """Get orchestration metrics snapshot."""
        async with self._lock:
            return {
                "total_events": self.orchestration_metrics.total_events,
                "accepted_events": self.orchestration_metrics.accepted_events,
                "rejected_events": self.orchestration_metrics.rejected_events,
                "deferred_events": self.orchestration_metrics.deferred_events,
                "escalated_events": self.orchestration_metrics.escalated_events,
                "acceptance_rate": self.orchestration_metrics.get_acceptance_rate(),
                "policy_vetoes": self.orchestration_metrics.policy_vetoes,
                "policy_defers": self.orchestration_metrics.policy_defers
            }
