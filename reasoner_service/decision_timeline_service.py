"""
Decision Timeline Service

Records and replays all decision-related events for audit and analysis.

CRITICAL DISCLAIMER: This service records events only and does not influence live decisions.
It provides an immutable audit trail of trading decisions and outcomes for analysis, compliance,
and debugging purposes only.

Event Sourcing Model:
- All decisions are represented as a sequence of events
- Events are append-only (immutable once recorded)
- Events can be replayed to reconstruct decision state at any point
- No past events can be modified or deleted
- Timeline provides complete decision history with timestamps and correlation IDs

Events Support:
- SIGNAL_DETECTED: Trading signal identified by strategy
- DECISION_PROPOSED: Decision proposed based on signal
- POLICY_EVALUATED: Policy compliance checked (shadow mode)
- POLICY_CONFIDENCE_SCORED: Policy confidence calculated
- GOVERNANCE_EVALUATED: Governance rules checked (shadow mode)
- TRADE_EXECUTED: Trade executed (live or hypothetical)
- OUTCOME_RECORDED: Trade outcome recorded

Replay Semantics:
- Replay reconstructs full decision history by replaying events chronologically
- Replay is deterministic (same events → same sequence every time)
- Replay supports analysis, debugging, and compliance verification
- Replay never affects live trading
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from copy import deepcopy
import threading

logger = logging.getLogger(__name__)


class DecisionTimelineService:
    """
    Records and replays decision-related events in append-only timeline.
    
    This service maintains an immutable audit trail of all decision events,
    enabling analysis, debugging, and compliance verification without
    affecting live trading behavior.
    
    CONSTRAINTS:
    - Append-only event recording
    - No mutation of past events
    - Deterministic event sequencing
    - Fail-silent error handling
    - No influence on live decisions
    """
    
    # Supported event types
    VALID_EVENT_TYPES = {
        "SIGNAL_DETECTED",
        "DECISION_PROPOSED",
        "POLICY_EVALUATED",
        "POLICY_CONFIDENCE_SCORED",
        "GOVERNANCE_EVALUATED",
        "TRADE_EXECUTED",
        "OUTCOME_RECORDED",
    }
    
    def __init__(self):
        """
        Initialize the decision timeline service.
        
        Uses a thread-safe dictionary to store timelines by correlation_id.
        Each timeline is append-only.
        """
        self._timelines: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()  # Thread-safe access to timelines
        self._event_count = 0
    
    def record_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """
        Append an immutable event to the timeline.
        
        Args:
            event_type: Type of event (must be in VALID_EVENT_TYPES)
            payload: Event data dictionary
            correlation_id: Decision/trade identifier for correlation
        
        Returns:
            None (fire-and-forget recording)
        
        Raises:
            No exceptions raised (fail-silent)
        """
        try:
            if not event_type or not isinstance(event_type, str):
                logger.warning(f"Invalid event_type: {event_type}")
                return
            
            if event_type not in self.VALID_EVENT_TYPES:
                logger.warning(f"Unknown event_type: {event_type}, recording anyway")
            
            if not correlation_id or not isinstance(correlation_id, str):
                logger.warning(f"Invalid correlation_id: {correlation_id}")
                return
            
            if not isinstance(payload, dict):
                logger.warning(f"Payload must be dict, got {type(payload)}")
                return
            
            # Create immutable event (deep copy to prevent external mutation)
            event = {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": deepcopy(payload),
                "correlation_id": correlation_id,
                "sequence_number": self._event_count,
            }
            
            # Thread-safe append
            with self._lock:
                if correlation_id not in self._timelines:
                    self._timelines[correlation_id] = []
                
                self._timelines[correlation_id].append(event)
                self._event_count += 1
                
                logger.debug(
                    f"Recorded event {event_type} for {correlation_id} "
                    f"(seq: {event['sequence_number']})"
                )
        
        except Exception as e:
            logger.exception(f"Error recording event: {e}")
            # Fail-silent: return without raising
    
    def get_timeline(self, correlation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all events for a decision/trade in chronological order.
        
        Args:
            correlation_id: Decision/trade identifier
        
        Returns:
            List of events (read-only copies), empty list if not found
        """
        try:
            if not correlation_id or not isinstance(correlation_id, str):
                logger.warning(f"Invalid correlation_id: {correlation_id}")
                return []
            
            with self._lock:
                timeline = self._timelines.get(correlation_id, [])
                # Return deep copy to prevent external mutation
                return deepcopy(timeline)
        
        except Exception as e:
            logger.exception(f"Error retrieving timeline: {e}")
            return []
    
    def replay(self, correlation_id: str) -> List[Dict[str, Any]]:
        """
        Alias for get_timeline with explicit replay semantics.
        
        Replays all events for a decision/trade in order, enabling
        deterministic reconstruction of decision state at any point.
        
        Args:
            correlation_id: Decision/trade identifier
        
        Returns:
            List of events in chronological order, empty list if not found
        """
        return self.get_timeline(correlation_id)
    
    def get_event_count(self, correlation_id: Optional[str] = None) -> int:
        """
        Get event count for a correlation_id or globally.
        
        Args:
            correlation_id: Optional - if provided, count for that ID only
        
        Returns:
            Number of events
        """
        try:
            with self._lock:
                if correlation_id:
                    return len(self._timelines.get(correlation_id, []))
                return sum(len(events) for events in self._timelines.values())
        except Exception as e:
            logger.exception(f"Error counting events: {e}")
            return 0
    
    def get_all_correlation_ids(self) -> List[str]:
        """
        Get all correlation IDs with recorded events.
        
        Returns:
            List of correlation IDs (sorted)
        """
        try:
            with self._lock:
                return sorted(self._timelines.keys())
        except Exception as e:
            logger.exception(f"Error getting correlation IDs: {e}")
            return []
    
    def export_timeline(self, correlation_id: str) -> Dict[str, Any]:
        """
        Export complete timeline with metadata.
        
        Args:
            correlation_id: Decision/trade identifier
        
        Returns:
            Dict with timeline metadata and events
        """
        try:
            timeline = self.get_timeline(correlation_id)
            
            if not timeline:
                return {
                    "correlation_id": correlation_id,
                    "found": False,
                    "event_count": 0,
                    "events": [],
                }
            
            # Extract event types for summary
            event_types = [e["event_type"] for e in timeline]
            
            return {
                "correlation_id": correlation_id,
                "found": True,
                "event_count": len(timeline),
                "event_types": event_types,
                "first_event_time": timeline[0]["timestamp"] if timeline else None,
                "last_event_time": timeline[-1]["timestamp"] if timeline else None,
                "events": timeline,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This timeline records decision events only. "
                    "It does not influence live trading decisions."
                ),
            }
        except Exception as e:
            logger.exception(f"Error exporting timeline: {e}")
            return {
                "correlation_id": correlation_id,
                "found": False,
                "error": str(e),
            }
    
    def get_events_by_type(
        self,
        correlation_id: str,
        event_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Filter events by type within a correlation.
        
        Args:
            correlation_id: Decision/trade identifier
            event_type: Event type to filter by
        
        Returns:
            List of matching events in order
        """
        try:
            timeline = self.get_timeline(correlation_id)
            return [e for e in timeline if e["event_type"] == event_type]
        except Exception as e:
            logger.exception(f"Error filtering events: {e}")
            return []
    
    def validate_timeline(self, correlation_id: str) -> Dict[str, Any]:
        """
        Validate timeline integrity (sequence numbers, timestamps).
        
        Args:
            correlation_id: Decision/trade identifier
        
        Returns:
            Validation report dict
        """
        try:
            timeline = self.get_timeline(correlation_id)
            
            if not timeline:
                return {
                    "correlation_id": correlation_id,
                    "valid": False,
                    "reason": "Timeline not found",
                }
            
            issues = []
            
            # Check sequence numbers are monotonic
            for i, event in enumerate(timeline):
                seq = event.get("sequence_number")
                if seq is None:
                    issues.append(f"Event {i}: missing sequence_number")
                elif seq < (timeline[i - 1].get("sequence_number", -1) if i > 0 else -1):
                    issues.append(f"Event {i}: sequence number not monotonic")
            
            # Check timestamps are ordered (approximately)
            for i in range(1, len(timeline)):
                prev_ts = timeline[i - 1].get("timestamp", "")
                curr_ts = timeline[i].get("timestamp", "")
                if prev_ts > curr_ts:
                    issues.append(
                        f"Event {i}: timestamp before previous event "
                        f"({curr_ts} < {prev_ts})"
                    )
            
            # Check required fields
            for i, event in enumerate(timeline):
                required = ["event_type", "timestamp", "payload", "correlation_id"]
                for field in required:
                    if field not in event:
                        issues.append(f"Event {i}: missing {field}")
            
            return {
                "correlation_id": correlation_id,
                "valid": len(issues) == 0,
                "event_count": len(timeline),
                "issues": issues,
                "validated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.exception(f"Error validating timeline: {e}")
            return {
                "correlation_id": correlation_id,
                "valid": False,
                "error": str(e),
            }
    
    def clear_all(self) -> None:
        """
        Clear all recorded events (for testing only).
        
        WARNING: This is destructive and should only be used in test environments.
        """
        try:
            with self._lock:
                self._timelines.clear()
                self._event_count = 0
                logger.info("Cleared all timelines")
        except Exception as e:
            logger.exception(f"Error clearing timelines: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict with timeline statistics
        """
        try:
            with self._lock:
                total_events = sum(len(events) for events in self._timelines.values())
                total_correlations = len(self._timelines)
                
                # Event type distribution
                event_type_counts: Dict[str, int] = {}
                for timeline in self._timelines.values():
                    for event in timeline:
                        event_type = event.get("event_type", "UNKNOWN")
                        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
                
                return {
                    "total_events": total_events,
                    "total_correlations": total_correlations,
                    "event_type_distribution": event_type_counts,
                    "stats_generated_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.exception(f"Error getting statistics: {e}")
            return {"error": str(e)}
