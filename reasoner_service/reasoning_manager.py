"""
Bounded Reasoning Subsystem for DecisionOrchestrator.

This module implements a stateless reasoning manager that produces advisory signals
without mutating orchestrator or plan state. All reasoning operations are time-bounded
and read-only with respect to external systems.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Protocol, Union
)
from datetime import datetime


# ============================================================================
# ADVISORY SIGNAL SCHEMA
# ============================================================================

@dataclass
class AdvisorySignal:
    """Advisory signal produced by ReasoningManager.
    
    Represents a recommendation or flag from bounded reasoning.
    These are purely advisory and require orchestrator validation
    before affecting plan execution or state.
    """
    # REQUIRED FIELDS
    decision_id: str  # UUID v4 of the decision being reasoned
    signal_type: str  # e.g., 'action_suggestion', 'risk_flag', 'optimization_hint'
    payload: Dict[str, Any]  # Signal-specific data; never modifies orchestrator state
    
    # OPTIONAL FIELDS
    plan_id: Optional[str] = None  # UUID v4 of related plan, if any
    confidence: Optional[float] = None  # [0.0, 1.0] confidence score if applicable
    reasoning_mode: str = "default"  # Mode used for this reasoning
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))  # Unix ms
    error: Optional[str] = None  # Error message if reasoning failed
    metadata: Dict[str, Any] = field(default_factory=dict)  # Auxiliary data


# ============================================================================
# TYPE PROTOCOLS FOR REASONING FUNCTIONS
# ============================================================================

class ReasoningFunction(Protocol):
    """Protocol for user-provided reasoning functions."""
    
    async def __call__(
        self,
        event_payload: Dict[str, Any],
        context: Dict[str, Any],
        timeout_remaining_ms: int
    ) -> List[Dict[str, Any]]:
        """Execute reasoning logic.
        
        Args:
            event_payload: The event payload to reason about
            context: Read-only context dict with execution environment
            timeout_remaining_ms: Remaining time budget in milliseconds
            
        Returns:
            List of signal dicts with 'signal_type' and 'payload' keys.
            May be empty if no signals generated.
        """
        ...


class MemoryStore(Protocol):
    """Protocol for read-only memory access during reasoning."""
    
    async def get_historical_outcomes(
        self,
        plan_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve historical execution outcomes.
        
        Args:
            plan_id: Plan identifier
            limit: Maximum outcomes to retrieve
            
        Returns:
            List of outcome records (read-only)
        """
        ...
    
    async def get_context_value(
        self,
        key: str
    ) -> Optional[Any]:
        """Retrieve a context value by key.
        
        Args:
            key: Context key
            
        Returns:
            Value if exists, None otherwise
        """
        ...


# ============================================================================
# REASONING MANAGER CLASS
# ============================================================================

class ReasoningManager:
    """Bounded reasoning subsystem for stateless advisory generation.
    
    This manager produces AdvisorySignal objects without mutating
    orchestrator state, plan objects, or context. All reasoning operations
    are time-bounded and read-only.
    
    Attributes:
        modes: Dict mapping mode names to async reasoning functions
        memory_accessor: Read-only access to historical data
        timeout_ms: Maximum duration for a single reasoning call
        logger: Optional telemetry logger for reasoning events
    """
    
    def __init__(
        self,
        modes: Dict[str, Callable[[Dict[str, Any], Dict[str, Any], int], Any]],
        memory_accessor: Optional[MemoryStore] = None,
        timeout_ms: int = 5000,
        logger: Optional[Any] = None
    ):
        """Initialize ReasoningManager.
        
        Args:
            modes: Dict mapping mode names to async reasoning functions
            memory_accessor: Optional read-only memory store for historical context
            timeout_ms: Max reasoning duration in milliseconds (default 5s)
            logger: Optional logger for telemetry
        """
        self.modes = modes
        self.memory_accessor = memory_accessor
        self.timeout_ms = timeout_ms
        self.logger = logger
    
    async def reason(
        self,
        decision_id: str,
        event_payload: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None,
        reasoning_mode: str = "default",
        plan_id: Optional[str] = None
    ) -> List[AdvisorySignal]:
        """Produce advisory signals from bounded reasoning.
        
        This method is stateless - it never modifies orchestrator state,
        plan objects, or context. It returns purely advisory signals.
        
        Args:
            decision_id: UUID v4 of the decision being reasoned
            event_payload: Event payload to reason about
            execution_context: Read-only execution context dict
            reasoning_mode: Reasoning mode to use (default "default")
            plan_id: Optional UUID v4 of related plan
            
        Returns:
            List of AdvisorySignal objects (may be empty if no signals)
        """
        signals: List[AdvisorySignal] = []
        execution_context = execution_context or {}
        
        if not isinstance(event_payload, dict):
            return [
                AdvisorySignal(
                    decision_id=decision_id,
                    signal_type="error",
                    payload={},
                    plan_id=plan_id,
                    reasoning_mode=reasoning_mode,
                    error="invalid_event_payload_type"
                )
            ]
        
        # Check if reasoning mode exists
        if reasoning_mode not in self.modes:
            return [
                AdvisorySignal(
                    decision_id=decision_id,
                    signal_type="error",
                    payload={},
                    plan_id=plan_id,
                    reasoning_mode=reasoning_mode,
                    error=f"unknown_reasoning_mode: {reasoning_mode}"
                )
            ]
        
        try:
            # Create cancellation scope for timeout enforcement
            start_time_ms = int(time.time() * 1000)
            timeout_remaining_ms = self.timeout_ms
            
            reasoning_fn = self.modes[reasoning_mode]
            
            # Execute reasoning with timeout
            try:
                raw_signals = await asyncio.wait_for(
                    reasoning_fn(event_payload, execution_context, timeout_remaining_ms),
                    timeout=self.timeout_ms / 1000.0
                )
            except asyncio.TimeoutError:
                # Return timeout signal instead of throwing
                return [
                    AdvisorySignal(
                        decision_id=decision_id,
                        signal_type="timeout",
                        payload={"timeout_ms": self.timeout_ms},
                        plan_id=plan_id,
                        reasoning_mode=reasoning_mode,
                        error="reasoning_timeout_exceeded"
                    )
                ]
            
            # Validate and convert raw signals to AdvisorySignal objects
            if not isinstance(raw_signals, list):
                return [
                    AdvisorySignal(
                        decision_id=decision_id,
                        signal_type="error",
                        payload={},
                        plan_id=plan_id,
                        reasoning_mode=reasoning_mode,
                        error="invalid_reasoning_output_type"
                    )
                ]
            
            for idx, raw_signal in enumerate(raw_signals):
                try:
                    if not isinstance(raw_signal, dict):
                        signals.append(
                            AdvisorySignal(
                                decision_id=decision_id,
                                signal_type="error",
                                payload={"index": idx},
                                plan_id=plan_id,
                                reasoning_mode=reasoning_mode,
                                error="invalid_signal_type_in_list"
                            )
                        )
                        continue
                    
                    # Extract signal fields with validation
                    signal_type = raw_signal.get("signal_type", "unknown")
                    if not isinstance(signal_type, str):
                        signal_type = "unknown"
                    
                    payload = raw_signal.get("payload", {})
                    if not isinstance(payload, dict):
                        payload = {}
                    
                    confidence = raw_signal.get("confidence")
                    if confidence is not None:
                        try:
                            confidence = float(confidence)
                            if not (0.0 <= confidence <= 1.0):
                                confidence = None
                        except (ValueError, TypeError):
                            confidence = None
                    
                    signal = AdvisorySignal(
                        decision_id=decision_id,
                        signal_type=signal_type,
                        payload=payload,
                        plan_id=plan_id or raw_signal.get("plan_id"),
                        confidence=confidence,
                        reasoning_mode=reasoning_mode,
                        metadata=raw_signal.get("metadata", {})
                    )
                    signals.append(signal)
                
                except Exception as e:
                    # Record malformed signal but continue processing others
                    signals.append(
                        AdvisorySignal(
                            decision_id=decision_id,
                            signal_type="error",
                            payload={"index": idx, "error_detail": str(e)},
                            plan_id=plan_id,
                            reasoning_mode=reasoning_mode,
                            error="signal_construction_failed"
                        )
                    )
            
            # Log reasoning completion if logger available
            if self.logger:
                try:
                    elapsed_ms = int(time.time() * 1000) - start_time_ms
                    self.logger.log_reasoning_event(
                        decision_id=decision_id,
                        mode=reasoning_mode,
                        signal_count=len(signals),
                        elapsed_ms=elapsed_ms
                    )
                except Exception:
                    pass  # Never fail on logging
            
            return signals
        
        except Exception as e:
            # Catch-all: return error signal instead of throwing
            try:
                if self.logger:
                    self.logger.log_reasoning_error(
                        decision_id=decision_id,
                        mode=reasoning_mode,
                        error=str(e)
                    )
            except Exception:
                pass  # Never fail on logging
            
            return [
                AdvisorySignal(
                    decision_id=decision_id,
                    signal_type="error",
                    payload={},
                    plan_id=plan_id,
                    reasoning_mode=reasoning_mode,
                    error=f"reasoning_exception: {str(e)}"
                )
            ]
