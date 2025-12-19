"""
Policy Shadow Mode Integration

Integrates OutcomePolicyEvaluator into the decision cycle in observation-only mode:
- Evaluates policies on every decision
- Logs results for audit and analysis
- Does NOT block execution or mutate state
- Non-blocking error handling throughout

This is a dry-run validation phase. No enforcement until explicitly enabled.

INTEGRATION POINTS:
- Called from DecisionOrchestrator.process_decision after normalization
- Evaluator is initialized once during orchestrator setup
- Results logged to structured audit trail
- Future: PolicyStore can query history for enforcement decisions

NON-BREAKING DESIGN:
- Zero impact on existing decision flow
- Results captured in metadata dictionary
- No database writes (read-only via OutcomeStatsService)
- No side effects or state mutations
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyShadowModeManager:
    """
    Manages shadow mode execution of OutcomePolicyEvaluator.
    
    Responsibilities:
    - Initialize policy evaluator (lazy-loaded on first use)
    - Execute policy evaluation non-blockingly
    - Capture and log results
    - Handle errors gracefully
    - Maintain audit trail
    
    SHADOW MODE BEHAVIOR:
    - Evaluator is called on every decision
    - Results are logged but never block execution
    - VETO decisions are observed, not enforced
    - Execution always proceeds with or without evaluator
    
    FUTURE INTEGRATION POINTS:
    - PolicyStore can query evaluation history
    - Dashboard can visualize VETO patterns
    - A/B testing framework can compare policies
    - Decision enforcement rules can be developed from observations
    """
    
    def __init__(self):
        """Initialize shadow mode manager (evaluator created on demand)."""
        self._evaluator = None
        self._audit_trail = []  # In-memory log of all evaluations
        self._lock = asyncio.Lock()
        self._initialized = False
        self._init_error = None
    
    async def initialize(self, stats_service: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize policy evaluator (lazy, once per manager instance).
        
        Args:
            stats_service: OutcomeStatsService instance for querying metrics
            config: Optional configuration dict with policy parameters
        
        Returns:
            True if initialization successful, False otherwise
        
        DESIGN:
        - Non-blocking: Exceptions caught and logged
        - Lazy: Only happens on first call
        - Idempotent: Multiple calls are safe
        """
        if self._initialized:
            return self._evaluator is not None
        
        try:
            async with self._lock:
                # Double-check after acquiring lock
                if self._initialized:
                    return self._evaluator is not None
                
                # Import here to avoid circular dependency
                from reasoner_service.outcome_policy_evaluator import (
                    create_policy_evaluator,
                )
                
                logger.info("Initializing OutcomePolicyEvaluator for shadow mode")
                self._evaluator = create_policy_evaluator(stats_service, config or {})
                self._initialized = True
                logger.info("OutcomePolicyEvaluator initialized successfully")
                return True
        except Exception as e:
            self._init_error = str(e)
            self._initialized = True
            logger.exception("Failed to initialize OutcomePolicyEvaluator: %s", e)
            return False
    
    async def evaluate_decision(
        self,
        decision: Dict[str, Any],
        signal_type: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate decision using policy rules (shadow mode, non-blocking).
        
        Args:
            decision: Normalized decision dict from orchestrator
            signal_type: Signal type (extracted from decision if not provided)
            symbol: Trading symbol (extracted from decision if not provided)
            timeframe: Timeframe (extracted from decision if not provided)
        
        Returns:
            Dict with shadow mode evaluation results:
            {
                "evaluated": bool,  # True if evaluation was performed
                "decision": "allow" | "veto" | None,  # Policy decision
                "rule_name": str,  # Which rule made the decision (if veto)
                "reason": str,  # Human-readable reason (if veto)
                "metrics_snapshot": dict,  # Metrics used in evaluation
                "timestamp": str,  # ISO timestamp
                "error": str | None,  # If evaluation failed
                "audit_entry": dict,  # Full audit record
            }
        
        SHADOW MODE BEHAVIOR:
        - Results are logged but never block execution
        - Execution always proceeds regardless of VETO
        - This is observation-only for now
        
        FUTURE INTEGRATION:
        - PolicyStore can query this result and make enforcement decisions
        - Dashboard can visualize evaluation patterns
        - A/B testing framework can analyze effectiveness
        """
        result = {
            "evaluated": False,
            "decision": None,
            "rule_name": None,
            "reason": None,
            "metrics_snapshot": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "audit_entry": None,
        }
        
        if not self._evaluator:
            result["error"] = "evaluator_not_initialized"
            logger.warning("Policy evaluator not initialized, skipping shadow evaluation")
            return result
        
        try:
            # Extract signal metadata from decision if not provided
            sig_type = signal_type or decision.get("signal_type")
            sym = symbol or decision.get("symbol")
            tf = timeframe or decision.get("timeframe")
            
            # Evaluate policies
            eval_result = await self._evaluator.evaluate(sig_type, sym, tf)
            
            if eval_result:
                # VETO decision
                result["evaluated"] = True
                result["decision"] = eval_result.decision.value  # "veto"
                result["rule_name"] = eval_result.rule_name
                result["reason"] = eval_result.reason
                result["metrics_snapshot"] = eval_result.metrics_snapshot
                result["timestamp"] = eval_result.timestamp
                
                # Log veto to audit trail
                audit_entry = {
                    "timestamp": result["timestamp"],
                    "decision": result["decision"],
                    "rule_name": result["rule_name"],
                    "reason": result["reason"],
                    "signal_type": sig_type,
                    "symbol": sym,
                    "timeframe": tf,
                    "decision_id": decision.get("id"),
                    "recommendation": decision.get("recommendation"),
                    "confidence": decision.get("confidence"),
                }
                result["audit_entry"] = audit_entry
                self._audit_trail.append(audit_entry)
                
                logger.warning(
                    "POLICY VETO (shadow mode): rule=%s, signal_type=%s, symbol=%s, reason=%s",
                    result["rule_name"],
                    sig_type,
                    sym,
                    result["reason"],
                )
            else:
                # ALLOW decision (no rule veto)
                result["evaluated"] = True
                result["decision"] = "allow"
                audit_entry = {
                    "timestamp": result["timestamp"],
                    "decision": "allow",
                    "signal_type": sig_type,
                    "symbol": sym,
                    "timeframe": tf,
                    "decision_id": decision.get("id"),
                    "recommendation": decision.get("recommendation"),
                    "confidence": decision.get("confidence"),
                }
                result["audit_entry"] = audit_entry
                self._audit_trail.append(audit_entry)
                
                logger.debug(
                    "POLICY ALLOW (shadow mode): signal_type=%s, symbol=%s",
                    sig_type,
                    sym,
                )
        
        except Exception as e:
            result["error"] = str(e)
            result["evaluated"] = False
            logger.exception("Error during policy shadow evaluation: %s", e)
            # IMPORTANT: Non-blocking - continue to execution regardless
        
        return result
    
    async def get_audit_trail(self, limit: Optional[int] = 100) -> list:
        """
        Retrieve audit trail of policy evaluations.
        
        Args:
            limit: Maximum number of recent evaluations to return
        
        Returns:
            List of audit entries (most recent first)
        
        FUTURE USE:
        - Dashboard can query for visualization
        - Analytics can analyze VETO patterns
        - Testing framework can validate policies
        """
        async with self._lock:
            if limit is None:
                return list(reversed(self._audit_trail))
            return list(reversed(self._audit_trail[-limit:]))
    
    async def clear_audit_trail(self) -> int:
        """
        Clear audit trail (for testing only).
        
        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._audit_trail)
            self._audit_trail.clear()
            logger.info("Cleared %d audit trail entries", count)
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about policy evaluations.
        
        Returns:
            Dict with evaluation counts and patterns
        
        FUTURE USE:
        - Dashboard metrics
        - Health monitoring
        - Policy effectiveness analysis
        """
        if not self._audit_trail:
            return {
                "total_evaluations": 0,
                "allow_count": 0,
                "veto_count": 0,
                "veto_by_rule": {},
                "veto_by_signal_type": {},
            }
        
        veto_by_rule = {}
        veto_by_signal = {}
        veto_count = 0
        
        for entry in self._audit_trail:
            if entry.get("decision") == "veto":
                veto_count += 1
                rule = entry.get("rule_name", "unknown")
                veto_by_rule[rule] = veto_by_rule.get(rule, 0) + 1
                
                signal = entry.get("signal_type", "unknown")
                veto_by_signal[signal] = veto_by_signal.get(signal, 0) + 1
        
        return {
            "total_evaluations": len(self._audit_trail),
            "allow_count": len(self._audit_trail) - veto_count,
            "veto_count": veto_count,
            "veto_by_rule": veto_by_rule,
            "veto_by_signal_type": veto_by_signal,
            "veto_rate": veto_count / len(self._audit_trail) if self._audit_trail else 0.0,
        }


# Global shadow mode manager (singleton per process)
_shadow_mode_manager = PolicyShadowModeManager()


def get_shadow_mode_manager() -> PolicyShadowModeManager:
    """Get the global shadow mode manager instance."""
    return _shadow_mode_manager


async def initialize_shadow_mode(
    stats_service: Any,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Initialize global shadow mode manager.
    
    Called once from DecisionOrchestrator.setup().
    
    Args:
        stats_service: OutcomeStatsService instance
        config: Optional policy configuration
    
    Returns:
        True if successful, False otherwise
    """
    return await _shadow_mode_manager.initialize(stats_service, config)


async def evaluate_decision_shadow(
    decision: Dict[str, Any],
    signal_type: Optional[str] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate decision in shadow mode (wrapper function).
    
    Args:
        decision: Normalized decision from orchestrator
        signal_type: Signal type (optional, extracted from decision if not provided)
        symbol: Symbol (optional, extracted from decision if not provided)
        timeframe: Timeframe (optional, extracted from decision if not provided)
    
    Returns:
        Shadow mode evaluation result dict
    """
    return await _shadow_mode_manager.evaluate_decision(
        decision, signal_type, symbol, timeframe
    )


async def get_shadow_audit_trail(limit: Optional[int] = 100) -> list:
    """Get recent audit trail entries."""
    return await _shadow_mode_manager.get_audit_trail(limit)


def get_shadow_stats() -> Dict[str, Any]:
    """Get shadow mode statistics."""
    return _shadow_mode_manager.get_stats()
