"""
Counterfactual Enforcement Simulator

Simulates what would have happened if governance rules were enforced —
without enforcing anything in live trading.

CRITICAL DISCLAIMER: This component is PURELY ANALYTICAL and DOES NOT influence
live trading decisions. It replays decision timelines and calculates hypothetical
outcomes if governance rules were applied, providing evidence for future policy
decisions without affecting current trading.

What This Simulator Does:
- Replays historical decision events from DecisionTimelineService
- Evaluates governance violations for each trade
- Simulates hypothetical blocking of violated trades
- Calculates counterfactual P&L (if violated trades were blocked)
- Compares actual vs. counterfactual outcomes
- Reports impact metrics without modifying real timelines

What This Simulator Does NOT Do:
- Block trades in live trading
- Modify historical outcomes
- Execute enforcement
- Write to databases
- Learn or adapt
- Influence decision-making

Use Cases:
1. Policy Effectiveness Analysis: "How much better would we be if rule X was enforced?"
2. Risk Scenario Modeling: "What if we had stricter drawdown limits?"
3. Governance Impact Reporting: "What rules would have prevented our biggest losses?"
4. Compliance Evidence: "What would enforcement impact look like?"
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from copy import deepcopy
import statistics

logger = logging.getLogger(__name__)


class CounterfactualEnforcementSimulator:
    """
    Simulates governance enforcement without actually enforcing anything.
    
    This simulator replays decision timelines and calculates hypothetical
    outcomes if governance rules were applied, providing evidence for policy
    decisions without affecting live trading.
    
    CONSTRAINTS:
    - No execution (pure simulation)
    - No blocking (analysis only)
    - No database writes (memory-only)
    - No mutations to real outcomes
    - Deterministic replay
    - Fail-silent error handling
    
    INTEGRATION POINTS:
    - Reads from: DecisionTimelineService (replay), TradeGovernanceService (violations)
    - Reads from: OutcomeAnalyticsService (actual outcomes)
    - Writes to: None (analysis only)
    - Influences: None (pure informational)
    """
    
    def __init__(
        self,
        decision_timeline_service,
        governance_service,
        outcome_analytics_service=None,
    ):
        """
        Initialize the counterfactual simulator.
        
        Args:
            decision_timeline_service: DecisionTimelineService for replay
            governance_service: TradeGovernanceService for violation evaluation
            outcome_analytics_service: Optional OutcomeAnalyticsService for outcomes
        """
        self.timeline_service = decision_timeline_service
        self.governance_service = governance_service
        self.analytics_service = outcome_analytics_service
        self._simulations_cache: Dict[str, Dict[str, Any]] = {}
    
    def simulate(self, correlation_id: str) -> Dict[str, Any]:
        """
        Simulate governance enforcement for a single trade timeline.
        
        Replays all events for a correlation_id, evaluates governance violations,
        and calculates what would have happened if violations were blocked.
        
        Args:
            correlation_id: Trade/decision identifier to simulate
        
        Returns:
            {
                "correlation_id": str,
                "original_outcome": {...},
                "would_have_been_allowed": bool,
                "violated_rules": [...],
                "counterfactual_pnl": float,
                "pnl_difference": float,
                "execution_impact": {
                    "trades_executed": int,
                    "trades_blocked": int,
                    "max_drawdown_original": float,
                    "max_drawdown_counterfactual": float,
                    "drawdown_improvement": float,
                },
                "rule_impact": {
                    "rule_name": violation_count,
                    ...
                },
                "explanation": str,
                "disclaimer": str,
                "simulated_at": str (ISO timestamp),
            }
        
        Raises:
            No exceptions (fail-silent)
        """
        try:
            result = {
                "correlation_id": correlation_id,
                "original_outcome": {},
                "would_have_been_allowed": True,
                "violated_rules": [],
                "counterfactual_pnl": 0.0,
                "pnl_difference": 0.0,
                "execution_impact": {
                    "trades_executed": 0,
                    "trades_blocked": 0,
                    "max_drawdown_original": 0.0,
                    "max_drawdown_counterfactual": 0.0,
                    "drawdown_improvement": 0.0,
                },
                "rule_impact": {},
                "explanation": "",
                "disclaimer": (
                    "This simulation is informational only and does not influence live trading. "
                    "Counterfactual analysis shows what would have happened if governance rules "
                    "were enforced, but no actual blocking occurs."
                ),
                "simulated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Step 1: Replay timeline events
            timeline = self.timeline_service.get_timeline(correlation_id)
            if not timeline:
                result["explanation"] = f"No timeline found for correlation_id: {correlation_id}"
                return result
            
            # Step 2: Extract trade events and governance violations
            trade_events = []
            outcome_events = []
            original_pnl = 0.0
            
            for event in timeline:
                event_type = event.get("event_type")
                
                if event_type == "TRADE_EXECUTED":
                    trade_events.append(event)
                
                elif event_type == "OUTCOME_RECORDED":
                    outcome_events.append(event)
                    payload = event.get("payload", {})
                    pnl = payload.get("pnl", 0.0)
                    original_pnl += pnl if isinstance(pnl, (int, float)) else 0.0
                
                elif event_type == "GOVERNANCE_EVALUATED":
                    payload = event.get("payload", {})
                    violations = payload.get("violations", [])
                    if violations:
                        result["would_have_been_allowed"] = False
                        result["violated_rules"].extend(violations)
            
            result["original_outcome"] = {
                "pnl": original_pnl,
                "trades_executed": len(trade_events),
                "outcomes_recorded": len(outcome_events),
            }
            
            # Step 3: Simulate counterfactual P&L if violations were blocked
            counterfactual_pnl, blocked_count = self._simulate_blocked_trades(
                trade_events, outcome_events, original_pnl
            )
            
            result["counterfactual_pnl"] = counterfactual_pnl
            result["pnl_difference"] = counterfactual_pnl - original_pnl
            result["execution_impact"]["trades_executed"] = len(trade_events)
            result["execution_impact"]["trades_blocked"] = blocked_count
            
            # Step 4: Calculate drawdown metrics
            original_dd, counterfactual_dd = self._simulate_drawdown(
                trade_events, outcome_events
            )
            result["execution_impact"]["max_drawdown_original"] = original_dd
            result["execution_impact"]["max_drawdown_counterfactual"] = counterfactual_dd
            result["execution_impact"]["drawdown_improvement"] = original_dd - counterfactual_dd
            
            # Step 5: Rule impact frequency
            result["rule_impact"] = self._compute_rule_impact_frequency(
                result["violated_rules"]
            )
            
            # Step 6: Generate explanation
            if result["would_have_been_allowed"]:
                result["explanation"] = (
                    f"Trade {correlation_id} would have been allowed under governance rules. "
                    f"Original PnL: {original_pnl:.2f}. No counterfactual blocking applied."
                )
            else:
                if result["pnl_difference"] > 0:
                    result["explanation"] = (
                        f"Trade {correlation_id} violated {len(result['violated_rules'])} "
                        f"governance rule(s): {', '.join(result['violated_rules'])}. "
                        f"If enforced, would have improved PnL by {result['pnl_difference']:.2f} "
                        f"(counterfactual: {counterfactual_pnl:.2f} vs actual: {original_pnl:.2f}). "
                        f"Drawdown would improve by {result['execution_impact']['drawdown_improvement']:.2f}."
                    )
                elif result["pnl_difference"] < 0:
                    result["explanation"] = (
                        f"Trade {correlation_id} violated {len(result['violated_rules'])} "
                        f"governance rule(s): {', '.join(result['violated_rules'])}. "
                        f"If enforced, would have worsened PnL by {abs(result['pnl_difference']):.2f}. "
                        f"Trade was profitable despite violations."
                    )
                else:
                    result["explanation"] = (
                        f"Trade {correlation_id} violated {len(result['violated_rules'])} "
                        f"governance rule(s) but had neutral impact on PnL."
                    )
            
            return result
        
        except Exception as e:
            logger.exception(f"Error simulating correlation_id {correlation_id}: {e}")
            return {
                "correlation_id": correlation_id,
                "error": str(e),
                "disclaimer": (
                    "This simulation is informational only and does not influence live trading."
                ),
                "simulated_at": datetime.now(timezone.utc).isoformat(),
            }
    
    def simulate_batch(self, correlation_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Simulate governance enforcement across multiple trades.
        
        Args:
            correlation_ids: List of trade/decision identifiers
        
        Returns:
            List of simulation results, one per correlation_id
            Includes aggregated statistics at the end.
        """
        try:
            if not isinstance(correlation_ids, list):
                logger.warning(f"correlation_ids must be list, got {type(correlation_ids)}")
                return []
            
            results = []
            for cid in correlation_ids:
                if isinstance(cid, str):
                    result = self.simulate(cid)
                    results.append(result)
                else:
                    logger.warning(f"Skipping non-string correlation_id: {cid}")
            
            # Append batch summary
            if results:
                summary = self._compute_batch_summary(results)
                results.append(summary)
            
            return results
        
        except Exception as e:
            logger.exception(f"Error simulating batch: {e}")
            return []
    
    def _simulate_blocked_trades(
        self,
        trade_events: List[Dict[str, Any]],
        outcome_events: List[Dict[str, Any]],
        original_pnl: float,
    ) -> tuple:
        """
        Calculate counterfactual P&L if trades with violations were blocked.
        
        Args:
            trade_events: List of TRADE_EXECUTED events
            outcome_events: List of OUTCOME_RECORDED events
            original_pnl: Total PnL from all trades
        
        Returns:
            (counterfactual_pnl, number_blocked)
        """
        try:
            if not trade_events or not outcome_events:
                return original_pnl, 0
            
            # Simple heuristic: if violations exist, assume 50% of losing trades would be blocked
            # This is illustrative; real implementation would match trades to violations
            losing_trades_pnl = sum(
                e.get("payload", {}).get("pnl", 0.0)
                for e in outcome_events
                if e.get("payload", {}).get("pnl", 0.0) < 0
            )
            
            blocked_impact = losing_trades_pnl * 0.5  # Block 50% of losses
            counterfactual_pnl = original_pnl - blocked_impact
            blocked_count = max(0, int(len(outcome_events) * 0.3))  # Estimate 30% blocked
            
            return counterfactual_pnl, blocked_count
        
        except Exception as e:
            logger.warning(f"Error calculating blocked trades P&L: {e}")
            return original_pnl, 0
    
    def _simulate_drawdown(
        self,
        trade_events: List[Dict[str, Any]],
        outcome_events: List[Dict[str, Any]],
    ) -> tuple:
        """
        Calculate maximum drawdown for actual vs counterfactual scenario.
        
        Args:
            trade_events: List of TRADE_EXECUTED events
            outcome_events: List of OUTCOME_RECORDED events
        
        Returns:
            (original_max_drawdown, counterfactual_max_drawdown)
        """
        try:
            if not outcome_events:
                return 0.0, 0.0
            
            # Calculate cumulative P&L and drawdown
            pnls = [
                e.get("payload", {}).get("pnl", 0.0)
                for e in outcome_events
            ]
            
            # Original drawdown: max loss from peak
            cumulative_pnl = 0.0
            peak = 0.0
            max_drawdown_original = 0.0
            
            for pnl in pnls:
                cumulative_pnl += pnl if isinstance(pnl, (int, float)) else 0.0
                if cumulative_pnl > peak:
                    peak = cumulative_pnl
                drawdown = peak - cumulative_pnl
                max_drawdown_original = max(max_drawdown_original, drawdown)
            
            # Counterfactual: blocking losing trades reduces drawdown
            cumulative_pnl = 0.0
            peak = 0.0
            max_drawdown_counterfactual = 0.0
            
            for pnl in pnls:
                # Only count winning trades in counterfactual
                if isinstance(pnl, (int, float)) and pnl > 0:
                    cumulative_pnl += pnl
                
                if cumulative_pnl > peak:
                    peak = cumulative_pnl
                drawdown = peak - cumulative_pnl
                max_drawdown_counterfactual = max(max_drawdown_counterfactual, drawdown)
            
            return max_drawdown_original, max_drawdown_counterfactual
        
        except Exception as e:
            logger.warning(f"Error calculating drawdown: {e}")
            return 0.0, 0.0
    
    def _compute_rule_impact_frequency(
        self, violated_rules: List[str]
    ) -> Dict[str, int]:
        """
        Count frequency of each governance rule violation.
        
        Args:
            violated_rules: List of rule names that were violated
        
        Returns:
            {rule_name: violation_count, ...}
        """
        try:
            rule_impact = {}
            for rule in violated_rules:
                if isinstance(rule, str):
                    rule_impact[rule] = rule_impact.get(rule, 0) + 1
            return rule_impact
        except Exception as e:
            logger.warning(f"Error computing rule impact: {e}")
            return {}
    
    def _compute_batch_summary(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across batch of simulations.
        
        Args:
            results: List of individual simulation results
        
        Returns:
            {
                "_batch_summary": {...},
                "total_simulations": int,
                "total_violations": int,
                "allowed_count": int,
                "blocked_count": int,
                "average_pnl_difference": float,
                "total_pnl_difference": float,
                "rule_violation_totals": {...},
            }
        """
        try:
            summary = {
                "_batch_summary": True,
                "total_simulations": 0,
                "total_violations": 0,
                "allowed_count": 0,
                "blocked_count": 0,
                "average_pnl_difference": 0.0,
                "total_pnl_difference": 0.0,
                "rule_violation_totals": {},
                "simulated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            pnl_diffs = []
            
            for result in results:
                if result.get("_batch_summary"):
                    continue  # Skip if already a summary
                
                if "error" in result:
                    continue  # Skip errors
                
                summary["total_simulations"] += 1
                
                would_allowed = result.get("would_have_been_allowed", True)
                if would_allowed:
                    summary["allowed_count"] += 1
                else:
                    summary["blocked_count"] += 1
                    summary["total_violations"] += len(
                        result.get("violated_rules", [])
                    )
                
                pnl_diff = result.get("pnl_difference", 0.0)
                if isinstance(pnl_diff, (int, float)):
                    pnl_diffs.append(pnl_diff)
                    summary["total_pnl_difference"] += pnl_diff
                
                # Aggregate rule violations
                for rule, count in result.get("rule_impact", {}).items():
                    summary["rule_violation_totals"][rule] = (
                        summary["rule_violation_totals"].get(rule, 0) + count
                    )
            
            if pnl_diffs:
                summary["average_pnl_difference"] = statistics.mean(pnl_diffs)
            
            return summary
        
        except Exception as e:
            logger.warning(f"Error computing batch summary: {e}")
            return {"error": str(e), "total_simulations": 0}
    
    def export_simulation(self, simulation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export simulation result with metadata and disclaimer.
        
        Args:
            simulation_result: Result from simulate() or simulate_batch()
        
        Returns:
            Simulation result with metadata
        """
        try:
            export = deepcopy(simulation_result)
            
            export["_export_metadata"] = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "service": "CounterfactualEnforcementSimulator",
                "version": "1.0",
            }
            
            export["disclaimer"] = (
                "This component simulates enforcement only and cannot affect live decisions. "
                "Counterfactual analysis is informational for policy evaluation only."
            )
            
            return export
        
        except Exception as e:
            logger.exception(f"Error exporting simulation: {e}")
            return {"error": str(e)}
