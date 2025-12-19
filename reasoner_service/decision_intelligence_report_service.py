"""
Decision Intelligence Report Service

Aggregates outputs from existing shadow-mode analysis services to produce
an informational "decision intelligence report" describing trade quality,
risk, and confidence.

CRITICAL DISCLAIMER: This service is PURELY INFORMATIONAL and READ-ONLY.
It provides analytical intelligence only, never enforcement, blocking, or
execution capabilities.

KEY PRINCIPLES:
- Pure aggregation of existing shadow-mode services
- Zero enforcement or blocking logic
- Deterministic outputs (same inputs always produce same outputs)
- Fail-silent error handling (graceful degradation)
- No mutations to input services
- No learning or adaptive behavior
- Comprehensive disclaimers on all outputs

The report includes:
- confidence_score: Overall confidence in the trade (0-100)
- governance_pressure: Level of governance violations (none/low/medium/high)
- counterfactual_regret: Numeric regret metric
- risk_flags: List of informational risk indicators
- explanation: Human-readable analysis
- evaluated_at: ISO timestamp
- disclaimer: Explicit non-enforcement guarantee

This service enables human-informed decision-making through analysis,
not autonomous enforcement.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from copy import deepcopy
import statistics

logger = logging.getLogger(__name__)


class DecisionIntelligenceReportService:
    """
    Aggregates analysis from all shadow-mode services to generate
    informational "decision intelligence reports."
    
    This service is PURELY READ-ONLY and INFORMATIONAL:
    - No execution logic
    - No enforcement logic
    - No blocking or allow/deny decisions
    - No orchestrator access
    - No database writes
    - No mutation of inputs
    - No learning or adaptive behavior
    
    All outputs are deterministic and explicitly non-actionable.
    
    CONSTRAINTS:
    - Read-only access to all input services
    - Fail-silent on any service failure
    - Deterministic outputs
    - No state mutations
    - No side effects
    - Comprehensive disclaimers
    """
    
    def __init__(
        self,
        timeline_service,
        governance_service,
        counterfactual_simulator,
        policy_confidence_evaluator,
        outcome_analytics_service,
    ):
        """
        Initialize the decision intelligence service.
        
        Args:
            timeline_service: DecisionTimelineService (read-only)
            governance_service: TradeGovernanceService (read-only)
            counterfactual_simulator: CounterfactualEnforcementSimulator (read-only)
            policy_confidence_evaluator: PolicyConfidenceEvaluator (read-only)
            outcome_analytics_service: OutcomeAnalyticsService (read-only)
        
        DESIGN NOTE: All dependencies are read-only aggregators.
        No state is maintained in this service.
        """
        self.timeline_service = timeline_service
        self.governance_service = governance_service
        self.counterfactual_simulator = counterfactual_simulator
        self.policy_confidence_evaluator = policy_confidence_evaluator
        self.outcome_analytics_service = outcome_analytics_service
    
    def generate_report(self, correlation_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive decision intelligence report for a single trade.
        
        This method aggregates analysis from all shadow-mode services and produces
        an informational report describing trade quality, risk, and confidence.
        
        CRITICAL: This report is PURELY INFORMATIONAL and cannot influence live trading.
        It provides analysis only for human review and decision-making.
        
        Args:
            correlation_id: Trade identifier to analyze
        
        Returns:
            {
                "correlation_id": str,
                "confidence_score": float (0-100),
                "governance_pressure": str (none/low/medium/high),
                "counterfactual_regret": float,
                "risk_flags": list[str],
                "explanation": str,
                "evaluated_at": str (ISO timestamp),
                "disclaimer": str,
            }
        
        Raises:
            No exceptions (fail-silent, always returns valid report)
        """
        try:
            # Initialize report structure
            report = {
                "correlation_id": str(correlation_id) if correlation_id else "unknown",
                "confidence_score": 50.0,  # Default baseline
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": "",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This report is informational only and does not influence live trading. "
                    "It provides analytical intelligence for human review and decision-making only. "
                    "No enforcement, blocking, or execution occurs based on this report."
                ),
            }
            
            # Step 1: Gather data from all services (read-only)
            timeline_data = self._get_timeline_data(correlation_id)
            governance_data = self._get_governance_data(correlation_id)
            counterfactual_data = self._get_counterfactual_data(correlation_id)
            policy_data = self._get_policy_data(correlation_id)
            
            # Step 2: Calculate confidence score
            confidence = self._calculate_confidence_score(
                timeline_data, governance_data, counterfactual_data, policy_data
            )
            report["confidence_score"] = confidence
            
            # Step 3: Determine governance pressure
            pressure = self._determine_governance_pressure(governance_data)
            report["governance_pressure"] = pressure
            
            # Step 4: Calculate counterfactual regret
            regret = self._calculate_counterfactual_regret(counterfactual_data)
            report["counterfactual_regret"] = regret
            
            # Step 5: Identify risk flags
            flags = self._identify_risk_flags(
                timeline_data, governance_data, counterfactual_data
            )
            report["risk_flags"] = flags
            
            # Step 6: Generate explanation
            explanation = self._generate_explanation(
                correlation_id, confidence, pressure, regret, flags
            )
            report["explanation"] = explanation
            
            return report
        
        except Exception as e:
            logger.exception(f"Error generating report for {correlation_id}: {e}")
            # Fail-silent: return minimal valid report
            return {
                "correlation_id": str(correlation_id) if correlation_id else "unknown",
                "confidence_score": 25.0,  # Low confidence on error
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": ["Unable to fully analyze"],
                "explanation": f"Report generation encountered an error but completed gracefully.",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This report is informational only and does not influence live trading. "
                    "Error occurred during analysis."
                ),
            }
    
    def generate_batch(self, correlation_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Generate reports for multiple trades.
        
        Args:
            correlation_ids: List of trade identifiers
        
        Returns:
            List of individual reports with batch summary as final item
        """
        try:
            if not isinstance(correlation_ids, list):
                logger.warning(f"correlation_ids must be list, got {type(correlation_ids)}")
                return []
            
            reports = []
            
            # Generate individual reports
            for cid in correlation_ids:
                if isinstance(cid, str):
                    report = self.generate_report(cid)
                    reports.append(report)
                else:
                    logger.warning(f"Skipping non-string correlation_id: {cid}")
            
            # Append batch summary
            if reports:
                summary = self._compute_batch_summary(reports)
                reports.append(summary)
            
            return reports
        
        except Exception as e:
            logger.exception(f"Error generating batch: {e}")
            return []
    
    def _get_timeline_data(self, correlation_id: str) -> Dict[str, Any]:
        """
        Retrieve timeline events (read-only deepcopy).
        
        Args:
            correlation_id: Trade identifier
        
        Returns:
            Dictionary with timeline analysis
        """
        try:
            timeline = self.timeline_service.get_timeline(correlation_id)
            
            # Safe to work with (already deepcopied by service)
            analysis = {
                "events_count": len(timeline) if timeline else 0,
                "outcome_pnl": 0.0,
                "has_governance_eval": False,
                "has_policy_eval": False,
                "has_trade_executed": False,
                "raw_events": timeline or [],
            }
            
            # Extract PnL and event types
            for event in timeline or []:
                event_type = event.get("event_type", "")
                payload = event.get("payload", {})
                
                if event_type == "OUTCOME_RECORDED":
                    pnl = payload.get("pnl", 0.0)
                    if isinstance(pnl, (int, float)):
                        analysis["outcome_pnl"] = pnl
                
                elif event_type == "GOVERNANCE_EVALUATED":
                    analysis["has_governance_eval"] = True
                
                elif event_type == "POLICY_EVALUATED":
                    analysis["has_policy_eval"] = True
                
                elif event_type == "TRADE_EXECUTED":
                    analysis["has_trade_executed"] = True
            
            return analysis
        
        except Exception as e:
            logger.warning(f"Error getting timeline data: {e}")
            return {
                "events_count": 0,
                "outcome_pnl": 0.0,
                "has_governance_eval": False,
                "has_policy_eval": False,
                "has_trade_executed": False,
                "raw_events": [],
            }
    
    def _get_governance_data(self, correlation_id: str) -> Dict[str, Any]:
        """
        Retrieve governance evaluation (read-only).
        
        Args:
            correlation_id: Trade identifier
        
        Returns:
            Dictionary with governance analysis
        """
        try:
            trade_context = {"correlation_id": correlation_id}
            evaluation = self.governance_service.evaluate_trade(trade_context)
            
            analysis = {
                "violations": evaluation.get("violations", []),
                "violation_count": len(evaluation.get("violations", [])),
                "allowed": evaluation.get("allowed", True),  # Note: allowed/blocked are status, not actions
                "explanation": evaluation.get("explanation", ""),
            }
            
            return analysis
        
        except Exception as e:
            logger.warning(f"Error getting governance data: {e}")
            return {
                "violations": [],
                "violation_count": 0,
                "allowed": True,
                "explanation": "",
            }
    
    def _get_counterfactual_data(self, correlation_id: str) -> Dict[str, Any]:
        """
        Retrieve counterfactual simulation (read-only).
        
        Args:
            correlation_id: Trade identifier
        
        Returns:
            Dictionary with counterfactual analysis
        """
        try:
            simulation = self.counterfactual_simulator.simulate(correlation_id)
            
            analysis = {
                "would_have_been_allowed": simulation.get("would_have_been_allowed", True),
                "violated_rules": simulation.get("violated_rules", []),
                "counterfactual_pnl": simulation.get("counterfactual_pnl", 0.0),
                "pnl_difference": simulation.get("pnl_difference", 0.0),
                "rule_impact": simulation.get("rule_impact", {}),
            }
            
            return analysis
        
        except Exception as e:
            logger.warning(f"Error getting counterfactual data: {e}")
            return {
                "would_have_been_allowed": True,
                "violated_rules": [],
                "counterfactual_pnl": 0.0,
                "pnl_difference": 0.0,
                "rule_impact": {},
            }
    
    def _get_policy_data(self, correlation_id: str) -> Dict[str, Any]:
        """
        Retrieve policy confidence evaluation (read-only).
        
        Args:
            correlation_id: Trade identifier (not directly used by evaluator)
        
        Returns:
            Dictionary with policy analysis
        """
        try:
            # Policy evaluator analyzes policies, not specific trades
            # We'll use default policy analysis
            evaluation = self.policy_confidence_evaluator.evaluate_policy("default")
            
            analysis = {
                "confidence_score": evaluation.get("confidence_score", 0.5),
                "ready_for_enforcement": evaluation.get("ready_for_enforcement", False),
                "sample_size": evaluation.get("sample_size", 0),
            }
            
            return analysis
        
        except Exception as e:
            logger.warning(f"Error getting policy data: {e}")
            return {
                "confidence_score": 0.5,
                "ready_for_enforcement": False,
                "sample_size": 0,
            }
    
    def _calculate_confidence_score(
        self,
        timeline_data: Dict[str, Any],
        governance_data: Dict[str, Any],
        counterfactual_data: Dict[str, Any],
        policy_data: Dict[str, Any],
    ) -> float:
        """
        Calculate overall confidence score (0-100).
        
        This is purely analytical: high confidence means the trade is well-understood
        and aligns with governance rules, not that it should be executed.
        
        Args:
            timeline_data: Timeline analysis
            governance_data: Governance analysis
            counterfactual_data: Counterfactual analysis
            policy_data: Policy analysis
        
        Returns:
            Confidence score (0-100)
        """
        try:
            score = 50.0  # Baseline
            
            # Factor 1: Event completeness (max +20)
            events = timeline_data.get("events_count", 0)
            if events >= 4:  # Signal, Decision, Governance, Outcome
                score += 20
            elif events >= 3:
                score += 15
            elif events >= 2:
                score += 10
            
            # Factor 2: No violations (max +20)
            violation_count = governance_data.get("violation_count", 0)
            if violation_count == 0:
                score += 20
            elif violation_count == 1:
                score += 10
            elif violation_count > 3:
                score -= 10
            
            # Factor 3: Counterfactual alignment (max +20)
            # If counterfactual would have been allowed, high confidence
            if counterfactual_data.get("would_have_been_allowed"):
                score += 20
            else:
                # Violations suggest lower confidence
                score -= 10
            
            # Factor 4: Policy confidence (max +20)
            policy_confidence = policy_data.get("confidence_score", 0.5)
            score += policy_confidence * 20
            
            # Factor 5: Positive P&L (max +10)
            timeline_pnl = timeline_data.get("outcome_pnl", 0.0)
            if timeline_pnl > 0:
                score += 10
            elif timeline_pnl < -100:
                score -= 5
            
            # Clamp to 0-100 range
            score = max(0, min(100, score))
            
            return round(score, 1)
        
        except Exception as e:
            logger.warning(f"Error calculating confidence: {e}")
            return 50.0
    
    def _determine_governance_pressure(
        self, governance_data: Dict[str, Any]
    ) -> str:
        """
        Determine governance pressure level.
        
        Pressure reflects how many violations exist, not whether to enforce.
        
        Args:
            governance_data: Governance analysis
        
        Returns:
            One of: "none", "low", "medium", "high"
        """
        try:
            violation_count = governance_data.get("violation_count", 0)
            
            if violation_count == 0:
                return "none"
            elif violation_count == 1:
                return "low"
            elif violation_count <= 3:
                return "medium"
            else:
                return "high"
        
        except Exception as e:
            logger.warning(f"Error determining governance pressure: {e}")
            return "none"
    
    def _calculate_counterfactual_regret(
        self, counterfactual_data: Dict[str, Any]
    ) -> float:
        """
        Calculate counterfactual regret metric.
        
        Regret is how much better/worse P&L would have been if rules were enforced.
        Positive regret means we'd regret not enforcing. Negative means we'd regret enforcing.
        
        Args:
            counterfactual_data: Counterfactual analysis
        
        Returns:
            Regret metric (can be 0, positive, or negative)
        """
        try:
            # Regret = pnl_difference (what we'd miss if blocked)
            pnl_diff = counterfactual_data.get("pnl_difference", 0.0)
            
            if isinstance(pnl_diff, (int, float)):
                # If positive, we'd regret missing the profit (trade was good)
                # If negative, we'd regret the loss (trade was bad)
                return round(pnl_diff, 2)
            
            return 0.0
        
        except Exception as e:
            logger.warning(f"Error calculating regret: {e}")
            return 0.0
    
    def _identify_risk_flags(
        self,
        timeline_data: Dict[str, Any],
        governance_data: Dict[str, Any],
        counterfactual_data: Dict[str, Any],
    ) -> List[str]:
        """
        Identify informational risk flags.
        
        Flags are descriptive risk indicators, not enforcement decisions.
        They highlight aspects that warrant human review.
        
        Args:
            timeline_data: Timeline analysis
            governance_data: Governance analysis
            counterfactual_data: Counterfactual analysis
        
        Returns:
            List of risk flag strings
        """
        try:
            flags = []
            
            # Flag 1: Governance violations
            violations = governance_data.get("violations", [])
            if violations:
                flags.append(f"Governance violations detected: {len(violations)} rule(s)")
            
            # Flag 2: Large negative P&L
            timeline_pnl = timeline_data.get("outcome_pnl", 0.0)
            if timeline_pnl < -200:
                flags.append(f"Large loss: {timeline_pnl:.2f}")
            
            # Flag 3: Counterfactual would have blocked
            if not counterfactual_data.get("would_have_been_allowed"):
                blocked_rules = counterfactual_data.get("violated_rules", [])
                if blocked_rules:
                    flags.append(f"Would have been blocked: {blocked_rules[0]}")
            
            # Flag 4: Positive regret (we'd miss profit if blocked)
            regret = counterfactual_data.get("pnl_difference", 0.0)
            if regret > 150:
                flags.append("High counterfactual opportunity cost")
            
            # Flag 5: Sparse event timeline
            events = timeline_data.get("events_count", 0)
            if events < 2:
                flags.append("Limited event data for analysis")
            
            return flags
        
        except Exception as e:
            logger.warning(f"Error identifying risk flags: {e}")
            return []
    
    def _generate_explanation(
        self,
        correlation_id: str,
        confidence: float,
        pressure: str,
        regret: float,
        flags: List[str],
    ) -> str:
        """
        Generate human-readable explanation.
        
        Explanation describes the analysis transparently without suggesting actions.
        
        Args:
            correlation_id: Trade identifier
            confidence: Confidence score
            pressure: Governance pressure level
            regret: Counterfactual regret
            flags: Risk flags
        
        Returns:
            Explanation string
        """
        try:
            parts = []
            
            # Confidence summary
            if confidence >= 75:
                confidence_desc = "high confidence"
            elif confidence >= 50:
                confidence_desc = "moderate confidence"
            else:
                confidence_desc = "low confidence"
            
            parts.append(
                f"Trade {correlation_id} was analyzed with {confidence_desc} "
                f"({confidence:.0f}/100)."
            )
            
            # Governance summary
            if pressure == "none":
                parts.append("No governance violations detected.")
            elif pressure == "low":
                parts.append("Light governance pressure from minimal violations.")
            elif pressure == "medium":
                parts.append("Moderate governance pressure from multiple violations.")
            else:
                parts.append("Significant governance pressure from numerous violations.")
            
            # Counterfactual summary
            if regret > 0:
                parts.append(
                    f"Counterfactual analysis suggests {regret:.2f} "
                    f"in unrealized opportunity cost if rules were enforced."
                )
            elif regret < 0:
                parts.append(
                    f"Counterfactual analysis suggests {-regret:.2f} "
                    f"in avoided loss if rules were enforced."
                )
            
            # Risk summary
            if flags:
                flag_desc = "; ".join(flags[:2])  # Top 2 flags
                parts.append(f"Key observations: {flag_desc}")
            
            # Non-enforcement statement
            parts.append(
                "This analysis is provided for human review only. "
                "No enforcement or blocking occurs based on this report."
            )
            
            return " ".join(parts)
        
        except Exception as e:
            logger.warning(f"Error generating explanation: {e}")
            return "Analysis generated but explanation could not be created."
    
    def _compute_batch_summary(
        self, reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across batch of reports.
        
        Args:
            reports: List of individual reports (exclude summary)
        
        Returns:
            Batch summary dictionary
        """
        try:
            # Filter out any existing summaries
            individual_reports = [
                r for r in reports if not r.get("_batch_summary")
            ]
            
            if not individual_reports:
                return {
                    "_batch_summary": True,
                    "total_reports": 0,
                    "average_confidence": 0.0,
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                }
            
            # Extract metrics
            confidence_scores = [
                r.get("confidence_score", 50) 
                for r in individual_reports
                if isinstance(r.get("confidence_score"), (int, float))
            ]
            
            pressure_counts = {}
            total_risk_flags = 0
            total_regret = 0.0
            
            for report in individual_reports:
                pressure = report.get("governance_pressure", "none")
                pressure_counts[pressure] = pressure_counts.get(pressure, 0) + 1
                
                total_risk_flags += len(report.get("risk_flags", []))
                regret = report.get("counterfactual_regret", 0.0)
                if isinstance(regret, (int, float)):
                    total_regret += regret
            
            # Compute averages
            avg_confidence = statistics.mean(confidence_scores) if confidence_scores else 50.0
            
            summary = {
                "_batch_summary": True,
                "total_reports": len(individual_reports),
                "average_confidence": round(avg_confidence, 1),
                "governance_pressure_distribution": pressure_counts,
                "total_risk_flags": total_risk_flags,
                "average_regret": round(total_regret / len(individual_reports), 2),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            return summary
        
        except Exception as e:
            logger.exception(f"Error computing batch summary: {e}")
            return {
                "_batch_summary": True,
                "error": str(e),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }
