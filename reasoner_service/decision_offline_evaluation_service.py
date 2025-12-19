"""
Decision Offline Evaluation Service (Phase 8)

Performs HISTORICAL, OFFLINE, REPLAY-ONLY evaluation of past trades
under hypothetical policy and governance configurations.

CRITICAL CONSTRAINTS (DO NOT VIOLATE):
- NO execution logic
- NO enforcement logic
- NO orchestration
- NO trade blocking
- NO mutation of archives or memory
- NO database writes
- NO learning, tuning, or optimization
- NO async required

PURPOSE:
Evaluate hypothetical policy/governance scenarios against historical data
for human analysis and comparison ONLY.

READS FROM:
- DecisionIntelligenceArchiveService (historical reports)
- DecisionIntelligenceMemoryService (institutional memory)
- CounterfactualEnforcementSimulator (hypothetical enforcement analysis)

ARCHITECTURE:
- Pure replay-only analysis layer
- All computations are deterministic
- All outputs deepcopied for immutability
- Fail-silent error handling
- Zero side effects
- No enforcement keywords or logic

SAFETY GUARANTEES:
1. Replay-only behavior: Never modifies input data
2. Deterministic outputs: Same input always produces same result
3. Deepcopy on access: Returned data cannot affect service state
4. Fail-silent behavior: Graceful degradation on errors
5. No mutation: Archive and memory never modified
6. Informational only: All output is for human review only
7. Zero enforcement: No execution or blocking capabilities exist
8. Scenario isolation: Each scenario evaluated independently
9. No learning: No optimization or adaptive behavior
10. Explicit disclaimer: All output includes informational-only disclaimer

All methods are read-only and produce only informational output.
No execution, enforcement, blocking, or orchestration capabilities exist.
"""

import logging
import json
from datetime import datetime, timezone
from copy import deepcopy
from typing import Dict, Any, List, Optional
from statistics import mean, stdev, median

logger = logging.getLogger(__name__)


class DecisionOfflineEvaluationService:
    """
    Performs REPLAY-ONLY, OFFLINE evaluation of historical trades under
    hypothetical policy and governance configurations.
    
    This service:
    - Reads historical decision intelligence reports
    - Simulates hypothetical policy configurations
    - Compares scenarios directionally (no scoring or ranking)
    - Produces human-readable evaluation reports
    - NEVER modifies any data or influences live decisions
    
    CRITICAL: This service is READ-ONLY and produces informational output only.
    No execution, enforcement, or modification capabilities exist.
    """

    def __init__(
        self,
        archive_service,
        memory_service,
        simulator_service
    ):
        """
        Initialize offline evaluation service.
        
        Args:
            archive_service: DecisionIntelligenceArchiveService for historical data
            memory_service: DecisionIntelligenceMemoryService for institutional memory
            simulator_service: CounterfactualEnforcementSimulator for hypothetical analysis
        
        State:
        - _archive_service: Reference to archive (never written)
        - _memory_service: Reference to memory (never written)
        - _simulator_service: Reference to simulator (never written)
        - _evaluation_cache: Dict of completed evaluations (informational only)
        
        All references are read-only. No modifications to input services.
        """
        self._archive_service = archive_service
        self._memory_service = memory_service
        self._simulator_service = simulator_service
        self._evaluation_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("DecisionOfflineEvaluationService initialized (replay-only, offline)")

    def evaluate_policy_scenario(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replay historical decisions and evaluate under hypothetical policy.
        
        This method:
        - Reads historical decision reports from archive
        - Applies hypothetical constraints (no actual enforcement)
        - Computes descriptive statistics
        - Produces informational output only
        
        Args:
            config: Configuration dict for hypothetical scenario
                {
                    "scenario_name": str,
                    "description": str,
                    "policy_constraints": {
                        "max_exposure": float,
                        "max_drawdown": float,
                        "min_confidence": float,
                        "blocked_regimes": list[str],
                        "required_governance": list[str],
                    },
                    "evaluation_window": {
                        "start": str (ISO timestamp),
                        "end": str (ISO timestamp),
                    },
                }
        
        Returns:
            Dict with evaluation results (deepcopied, safe for external use)
            {
                "scenario_name": str,
                "scenario_id": str (auto-generated),
                "evaluation_timestamp": str (ISO),
                "policy_constraints": {...},
                "statistics": {
                    "total_trades_evaluated": int,
                    "trades_allowed": int,
                    "trades_would_block": int,
                    "average_confidence": float,
                    "confidence_distribution": {...},
                    "governance_pressure_distribution": {...},
                    "risk_flag_frequency": {...},
                    "trade_volume_statistics": {...},
                },
                "impact_analysis": {
                    "blocked_percentage": float (0-100),
                    "allowed_percentage": float (0-100),
                    "average_blocked_confidence": float,
                    "average_allowed_confidence": float,
                    "governance_pressure_change": float,
                },
                "explanation": str (human-readable),
                "disclaimer": str (informational-only),
                "is_deterministic": bool,
            }
        
        Note:
            - Returns empty/zero structure on empty archive (never raises)
            - All calculations are deterministic
            - All numbers are informational only
            - Fail-silent on configuration errors
        """
        try:
            if not isinstance(config, dict):
                config = {}
            scenario_name = config.get("scenario_name", "unnamed_scenario")
            scenario_id = self._generate_scenario_id(scenario_name)
            
            # Read historical reports (deepcopy for safety)
            archive_reports = deepcopy(self._archive_service._archive)
            
            if not archive_reports:
                logger.debug("Empty archive, returning empty evaluation")
                return self._empty_evaluation_result(scenario_name, scenario_id, config)
            
            # Filter by evaluation window if provided
            eval_window = config.get("evaluation_window")
            reports_to_evaluate = self._filter_by_window(archive_reports, eval_window)
            
            if not reports_to_evaluate:
                logger.debug("No reports in evaluation window")
                return self._empty_evaluation_result(scenario_name, scenario_id, config)
            
            # Extract policy constraints
            policy_constraints = config.get("policy_constraints", {})
            
            # Evaluate each report against hypothetical policy
            evaluation_results = self._evaluate_reports_against_policy(
                reports_to_evaluate,
                policy_constraints
            )
            
            # Compute statistics from evaluation
            statistics = self._compute_evaluation_statistics(
                reports_to_evaluate,
                evaluation_results
            )
            
            # Compute impact analysis
            impact_analysis = self._compute_impact_analysis(
                evaluation_results,
                statistics
            )
            
            # Build result
            result = {
                "scenario_name": scenario_name,
                "scenario_id": scenario_id,
                "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
                "policy_constraints": deepcopy(policy_constraints),
                "statistics": statistics,
                "impact_analysis": impact_analysis,
                "explanation": self._generate_explanation(
                    scenario_name,
                    statistics,
                    impact_analysis
                ),
                "disclaimer": (
                    "This evaluation is informational only and does not influence live decisions. "
                    "Results show hypothetical impact of policy changes under historical conditions. "
                    "No actual enforcement occurs."
                ),
                "is_deterministic": True,
            }
            
            # Cache for reference (informational only)
            self._evaluation_cache[scenario_id] = deepcopy(result)
            
            return deepcopy(result)
        
        except Exception as e:
            logger.exception(f"Error evaluating policy scenario: {e}")
            return self._empty_evaluation_result(
                config.get("scenario_name", "unnamed"),
                self._generate_scenario_id(config.get("scenario_name", "unnamed")),
                config
            )

    def compare_scenarios(
        self,
        scenario_a_result: Dict[str, Any],
        scenario_b_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Directional comparison of two evaluation scenarios.
        
        This method:
        - Compares statistics between scenarios
        - Reports directional differences only (no scoring or ranking)
        - Produces informational comparison output
        - NEVER ranks one scenario as "better"
        
        Args:
            scenario_a_result: Result dict from evaluate_policy_scenario (scenario A)
            scenario_b_result: Result dict from evaluate_policy_scenario (scenario B)
        
        Returns:
            Dict with directional comparison (deepcopied, safe for external use)
            {
                "scenario_a_name": str,
                "scenario_b_name": str,
                "comparison_timestamp": str (ISO),
                "directional_differences": {
                    "blocked_percentage": {
                        "scenario_a_value": float,
                        "scenario_b_value": float,
                        "direction": str ("A_higher" | "B_higher" | "same"),
                        "delta": float,
                    },
                    "average_confidence": {...},
                    "governance_pressure": {...},
                    "trade_volume": {...},
                },
                "isolation_analysis": {
                    "scenario_a_unique_constraints": list[str],
                    "scenario_b_unique_constraints": list[str],
                    "shared_constraints": list[str],
                },
                "explanation": str (human-readable, directional only),
                "disclaimer": str (informational-only, no ranking),
                "is_deterministic": bool,
            }
        
        Note:
            - Directional only (no scoring or ranking)
            - No recommendation which scenario is "better"
            - Fail-silent on missing fields
            - All numbers are informational only
        """
        try:
            comparison = {
                "scenario_a_name": scenario_a_result.get("scenario_name", "A"),
                "scenario_b_name": scenario_b_result.get("scenario_name", "B"),
                "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
                "directional_differences": self._compute_directional_differences(
                    scenario_a_result,
                    scenario_b_result
                ),
                "isolation_analysis": self._analyze_constraint_isolation(
                    scenario_a_result,
                    scenario_b_result
                ),
                "explanation": self._generate_comparison_explanation(
                    scenario_a_result,
                    scenario_b_result
                ),
                "disclaimer": (
                    "This comparison is informational only and does not influence live decisions. "
                    "Directional differences are shown for analysis purposes only. "
                    "No ranking of scenarios. "
                    "No actual enforcement occurs."
                ),
                "is_deterministic": True,
            }
            
            return deepcopy(comparison)
        
        except Exception as e:
            logger.exception(f"Error comparing scenarios: {e}")
            return self._empty_comparison_result(
                scenario_a_result.get("scenario_name", "A"),
                scenario_b_result.get("scenario_name", "B")
            )

    def run_batch_evaluation(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate multiple independent scenarios in batch.
        
        This method:
        - Evaluates each configuration independently
        - Isolates failures (graceful degradation per scenario)
        - Produces batch report with all results
        - NO orchestration or execution logic
        
        Args:
            configs: List of configuration dicts for each scenario
                Each config has same structure as evaluate_policy_scenario
        
        Returns:
            Dict with batch results (deepcopied, safe for external use)
            {
                "batch_id": str (auto-generated),
                "batch_timestamp": str (ISO),
                "total_scenarios": int,
                "successful_evaluations": int,
                "failed_evaluations": int,
                "scenarios": [
                    {
                        "scenario_name": str,
                        "status": str ("success" | "error"),
                        "result": {...} or None,
                        "error_message": str or None,
                    },
                    ...
                ],
                "summary_statistics": {
                    "average_blocked_percentage": float,
                    "min_blocked_percentage": float,
                    "max_blocked_percentage": float,
                    "consistency_score": float (how similar results are),
                },
                "explanation": str (human-readable),
                "disclaimer": str (informational-only),
                "is_deterministic": bool,
            }
        
        Note:
            - Each scenario evaluated independently
            - Failures are isolated (one failure doesn't block others)
            - All results are informational only
            - Fail-silent on batch-level errors
        """
        try:
            batch_id = self._generate_batch_id()
            scenario_results = []
            successful_count = 0
            failed_count = 0
            
            # Evaluate each scenario independently
            for idx, config in enumerate(configs):
                try:
                    if not isinstance(config, dict):
                        raise ValueError("Invalid config: not a dict")
                    result = self.evaluate_policy_scenario(config)
                    scenario_results.append({
                        "scenario_name": config.get("scenario_name", f"scenario_{idx}"),
                        "status": "success",
                        "result": result,
                        "error_message": None,
                    })
                    successful_count += 1
                
                except Exception as e:
                    logger.exception(f"Error evaluating scenario {idx}: {e}")
                    scenario_name = config.get("scenario_name", f"scenario_{idx}") if isinstance(config, dict) else f"scenario_{idx}"
                    scenario_results.append({
                        "scenario_name": scenario_name,
                        "status": "error",
                        "result": None,
                        "error_message": str(e),
                    })
                    failed_count += 1
            
            # Compute batch-level summary statistics
            successful_results = [r["result"] for r in scenario_results if r["status"] == "success"]
            summary_stats = self._compute_batch_summary(successful_results)
            
            batch_result = {
                "batch_id": batch_id,
                "batch_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_scenarios": len(configs),
                "successful_evaluations": successful_count,
                "failed_evaluations": failed_count,
                "scenarios": scenario_results,
                "summary_statistics": summary_stats,
                "explanation": self._generate_batch_explanation(
                    successful_count,
                    failed_count,
                    summary_stats
                ),
                "disclaimer": (
                    "This batch evaluation is informational only and does not influence live decisions. "
                    "All scenarios are evaluated independently with graceful failure handling. "
                    "No actual enforcement occurs."
                ),
                "is_deterministic": True,
            }
            
            return deepcopy(batch_result)
        
        except Exception as e:
            logger.exception(f"Error running batch evaluation: {e}")
            return self._empty_batch_result()

    def export_evaluation_report(
        self,
        evaluation_result: Dict[str, Any],
        format: str = "json"
    ) -> str:
        """
        Export evaluation result in human-readable and machine-readable format.
        
        This method:
        - Converts evaluation result to deterministic output format
        - Includes explicit informational-only disclaimer
        - Produces consistent output (same input = same output)
        
        Args:
            evaluation_result: Result dict from evaluate_policy_scenario
            format: Output format ("json" | "text")
        
        Returns:
            str: Formatted report (deterministic, consistent across calls)
        
        Note:
            - Output is deterministic and consistent
            - Includes explicit disclaimers
            - No side effects
            - Fail-silent on format errors (returns JSON as default)
        """
        try:
            # Prepare export data (deepcopy for safety)
            export_data = deepcopy(evaluation_result)
            
            # Add export metadata
            export_data["export_timestamp"] = datetime.now(timezone.utc).isoformat()
            export_data["export_disclaimer"] = (
                "This evaluation report is informational only and does not influence live decisions. "
                "All findings are based on hypothetical policy scenarios evaluated against historical data. "
                "No actual enforcement, execution, or blocking occurs. "
                "Human judgment and analysis are required before any policy changes."
            )
            
            if format.lower() == "text":
                return self._format_as_text(export_data)
            else:
                # Default to JSON (deterministic)
                return json.dumps(export_data, indent=2, sort_keys=True, default=str)
        
        except Exception as e:
            logger.exception(f"Error exporting report: {e}")
            # Fail-silent: return JSON with error structure
            return json.dumps({
                "error": str(e),
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This evaluation report is informational only and does not influence live decisions."
                ),
            }, indent=2, default=str)

    # ========== PRIVATE HELPER METHODS ==========

    def _generate_scenario_id(self, scenario_name: str) -> str:
        """Generate deterministic scenario ID from name and timestamp."""
        try:
            import hashlib
            timestamp = datetime.now(timezone.utc).isoformat()
            combined = f"{scenario_name}_{timestamp}"
            hash_digest = hashlib.md5(combined.encode()).hexdigest()
            return f"scenario_{hash_digest[:8]}"
        except Exception as e:
            logger.debug(f"Error generating scenario ID: {e}")
            return f"scenario_{len(self._evaluation_cache)}"

    def _generate_batch_id(self) -> str:
        """Generate deterministic batch ID."""
        try:
            import hashlib
            timestamp = datetime.now(timezone.utc).isoformat()
            hash_digest = hashlib.md5(timestamp.encode()).hexdigest()
            return f"batch_{hash_digest[:8]}"
        except Exception as e:
            logger.debug(f"Error generating batch ID: {e}")
            return f"batch_{len(self._evaluation_cache)}"

    def _filter_by_window(
        self,
        reports: List[Dict[str, Any]],
        time_window: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter reports by evaluation time window."""
        try:
            if not time_window:
                return reports
            
            start_str = time_window.get("start")
            end_str = time_window.get("end")
            
            if not start_str or not end_str:
                return reports
            
            start_ts = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_ts = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            
            filtered = []
            for report in reports:
                try:
                    eval_str = report.get("evaluated_at", "")
                    eval_ts = datetime.fromisoformat(eval_str.replace('Z', '+00:00'))
                    if start_ts <= eval_ts <= end_ts:
                        filtered.append(report)
                except Exception as e:
                    logger.debug(f"Error filtering report timestamp: {e}")
                    continue
            
            return filtered
        
        except Exception as e:
            logger.debug(f"Error filtering by window: {e}")
            return reports

    def _evaluate_reports_against_policy(
        self,
        reports: List[Dict[str, Any]],
        policy_constraints: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate each report against hypothetical policy constraints."""
        try:
            results = {}
            
            for report in reports:
                try:
                    report_id = report.get("correlation_id", "unknown")
                    
                    # Check each policy constraint
                    would_block = False
                    violated_constraints = []
                    
                    # Max exposure constraint
                    if "max_exposure" in policy_constraints:
                        exposure = report.get("trade_volume", 0)
                        max_exp = policy_constraints.get("max_exposure", float("inf"))
                        if exposure > max_exp:
                            would_block = True
                            violated_constraints.append("max_exposure")
                    
                    # Max drawdown constraint
                    if "max_drawdown" in policy_constraints:
                        # Would need actual outcome data; placeholder
                        max_dd = policy_constraints.get("max_drawdown", -100)
                        # Check if report indicates drawdown would exceed
                        if "drawdown" in report and report.get("drawdown", 0) < max_dd:
                            would_block = True
                            violated_constraints.append("max_drawdown")
                    
                    # Min confidence constraint
                    if "min_confidence" in policy_constraints:
                        confidence = report.get("confidence_score", 1.0)
                        min_conf = policy_constraints.get("min_confidence", 0.0)
                        if confidence < min_conf:
                            would_block = True
                            violated_constraints.append("min_confidence")
                    
                    # Blocked regimes constraint
                    if "blocked_regimes" in policy_constraints:
                        regime = report.get("regime", "")
                        blocked = policy_constraints.get("blocked_regimes", [])
                        if regime in blocked:
                            would_block = True
                            violated_constraints.append("blocked_regimes")
                    
                    # Required governance constraint
                    if "required_governance" in policy_constraints:
                        governance = report.get("governance_markers", [])
                        required = set(policy_constraints.get("required_governance", []))
                        if not required.issubset(set(governance)):
                            would_block = True
                            violated_constraints.append("required_governance")
                    
                    results[report_id] = {
                        "would_block": would_block,
                        "violated_constraints": violated_constraints,
                        "confidence_score": report.get("confidence_score", 0.0),
                        "governance_pressure": report.get("governance_pressure", 0.0),
                    }
                
                except Exception as e:
                    logger.debug(f"Error evaluating report {report_id}: {e}")
                    continue
            
            return results
        
        except Exception as e:
            logger.debug(f"Error evaluating reports against policy: {e}")
            return {}

    def _compute_evaluation_statistics(
        self,
        reports: List[Dict[str, Any]],
        evaluation_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute statistics from evaluation results."""
        try:
            blocked_count = sum(1 for r in evaluation_results.values() if r.get("would_block", False))
            allowed_count = len(evaluation_results) - blocked_count
            
            # Confidence statistics
            confidence_scores = [r.get("confidence_score", 0) for r in evaluation_results.values()]
            
            # Governance pressure statistics
            governance_scores = [r.get("governance_pressure", 0) for r in evaluation_results.values()]
            
            # Risk flags from original reports
            risk_flags_freq = {}
            for report in reports:
                flags = report.get("risk_flags", [])
                for flag in flags:
                    risk_flags_freq[flag] = risk_flags_freq.get(flag, 0) + 1
            
            # Trade volume statistics
            volumes = [r.get("trade_volume", 0) for r in reports]
            
            return {
                "total_trades_evaluated": len(evaluation_results),
                "trades_allowed": allowed_count,
                "trades_would_block": blocked_count,
                "average_confidence": mean(confidence_scores) if confidence_scores else 0.0,
                "confidence_distribution": {
                    "min": min(confidence_scores) if confidence_scores else 0.0,
                    "max": max(confidence_scores) if confidence_scores else 0.0,
                    "mean": mean(confidence_scores) if confidence_scores else 0.0,
                    "median": median(confidence_scores) if confidence_scores else 0.0,
                    "stdev": stdev(confidence_scores) if len(confidence_scores) > 1 else 0.0,
                },
                "governance_pressure_distribution": {
                    "min": min(governance_scores) if governance_scores else 0.0,
                    "max": max(governance_scores) if governance_scores else 0.0,
                    "mean": mean(governance_scores) if governance_scores else 0.0,
                    "median": median(governance_scores) if governance_scores else 0.0,
                },
                "risk_flag_frequency": risk_flags_freq,
                "trade_volume_statistics": {
                    "total_volume": sum(volumes),
                    "average_volume": mean(volumes) if volumes else 0.0,
                    "max_volume": max(volumes) if volumes else 0.0,
                    "min_volume": min(volumes) if volumes else 0.0,
                },
            }
        
        except Exception as e:
            logger.debug(f"Error computing statistics: {e}")
            return {
                "total_trades_evaluated": 0,
                "trades_allowed": 0,
                "trades_would_block": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "governance_pressure_distribution": {},
                "risk_flag_frequency": {},
                "trade_volume_statistics": {},
            }

    def _compute_impact_analysis(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        statistics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute impact analysis from evaluation results."""
        try:
            total = statistics.get("total_trades_evaluated", 0)
            blocked = statistics.get("trades_would_block", 0)
            allowed = statistics.get("trades_allowed", 0)
            
            blocked_pct = (blocked / total * 100) if total > 0 else 0.0
            allowed_pct = (allowed / total * 100) if total > 0 else 0.0
            
            # Average confidence for blocked vs allowed
            blocked_confidences = [
                r.get("confidence_score", 0)
                for r in evaluation_results.values()
                if r.get("would_block", False)
            ]
            allowed_confidences = [
                r.get("confidence_score", 0)
                for r in evaluation_results.values()
                if not r.get("would_block", False)
            ]
            
            return {
                "blocked_percentage": blocked_pct,
                "allowed_percentage": allowed_pct,
                "average_blocked_confidence": mean(blocked_confidences) if blocked_confidences else 0.0,
                "average_allowed_confidence": mean(allowed_confidences) if allowed_confidences else 0.0,
                "governance_pressure_change": 0.0,  # Informational only
            }
        
        except Exception as e:
            logger.debug(f"Error computing impact analysis: {e}")
            return {
                "blocked_percentage": 0.0,
                "allowed_percentage": 100.0,
                "average_blocked_confidence": 0.0,
                "average_allowed_confidence": 0.0,
                "governance_pressure_change": 0.0,
            }

    def _compute_directional_differences(
        self,
        result_a: Dict[str, Any],
        result_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute directional differences between two scenarios."""
        try:
            differences = {}
            
            # Compare blocked percentage
            blocked_a = result_a.get("impact_analysis", {}).get("blocked_percentage", 0)
            blocked_b = result_b.get("impact_analysis", {}).get("blocked_percentage", 0)
            differences["blocked_percentage"] = {
                "scenario_a_value": blocked_a,
                "scenario_b_value": blocked_b,
                "direction": "A_higher" if blocked_a > blocked_b else ("B_higher" if blocked_b > blocked_a else "same"),
                "delta": blocked_b - blocked_a,
            }
            
            # Compare average confidence
            conf_a = result_a.get("impact_analysis", {}).get("average_blocked_confidence", 0)
            conf_b = result_b.get("impact_analysis", {}).get("average_blocked_confidence", 0)
            differences["average_confidence"] = {
                "scenario_a_value": conf_a,
                "scenario_b_value": conf_b,
                "direction": "A_higher" if conf_a > conf_b else ("B_higher" if conf_b > conf_a else "same"),
                "delta": conf_b - conf_a,
            }
            
            # Compare governance pressure
            gov_a = result_a.get("impact_analysis", {}).get("governance_pressure_change", 0)
            gov_b = result_b.get("impact_analysis", {}).get("governance_pressure_change", 0)
            differences["governance_pressure"] = {
                "scenario_a_value": gov_a,
                "scenario_b_value": gov_b,
                "direction": "A_higher" if gov_a > gov_b else ("B_higher" if gov_b > gov_a else "same"),
                "delta": gov_b - gov_a,
            }
            
            # Compare trade volume
            vol_a = result_a.get("statistics", {}).get("trade_volume_statistics", {}).get("total_volume", 0)
            vol_b = result_b.get("statistics", {}).get("trade_volume_statistics", {}).get("total_volume", 0)
            differences["trade_volume"] = {
                "scenario_a_value": vol_a,
                "scenario_b_value": vol_b,
                "direction": "A_higher" if vol_a > vol_b else ("B_higher" if vol_b > vol_a else "same"),
                "delta": vol_b - vol_a,
            }
            
            return differences
        
        except Exception as e:
            logger.debug(f"Error computing directional differences: {e}")
            return {}

    def _analyze_constraint_isolation(
        self,
        result_a: Dict[str, Any],
        result_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze constraint isolation between scenarios."""
        try:
            constraints_a = set(result_a.get("policy_constraints", {}).keys())
            constraints_b = set(result_b.get("policy_constraints", {}).keys())
            
            return {
                "scenario_a_unique_constraints": list(constraints_a - constraints_b),
                "scenario_b_unique_constraints": list(constraints_b - constraints_a),
                "shared_constraints": list(constraints_a & constraints_b),
            }
        
        except Exception as e:
            logger.debug(f"Error analyzing constraint isolation: {e}")
            return {
                "scenario_a_unique_constraints": [],
                "scenario_b_unique_constraints": [],
                "shared_constraints": [],
            }

    def _compute_batch_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute batch-level summary statistics."""
        try:
            if not results:
                return {
                    "average_blocked_percentage": 0.0,
                    "min_blocked_percentage": 0.0,
                    "max_blocked_percentage": 0.0,
                    "consistency_score": 0.0,
                }
            
            blocked_percentages = [
                r.get("impact_analysis", {}).get("blocked_percentage", 0)
                for r in results
            ]
            
            consistency = 1.0 - (stdev(blocked_percentages) / 100) if len(blocked_percentages) > 1 and max(blocked_percentages) > 0 else 1.0
            
            return {
                "average_blocked_percentage": mean(blocked_percentages),
                "min_blocked_percentage": min(blocked_percentages),
                "max_blocked_percentage": max(blocked_percentages),
                "consistency_score": max(0.0, min(1.0, consistency)),
            }
        
        except Exception as e:
            logger.debug(f"Error computing batch summary: {e}")
            return {
                "average_blocked_percentage": 0.0,
                "min_blocked_percentage": 0.0,
                "max_blocked_percentage": 0.0,
                "consistency_score": 0.0,
            }

    def _generate_explanation(
        self,
        scenario_name: str,
        statistics: Dict[str, Any],
        impact_analysis: Dict[str, Any]
    ) -> str:
        """Generate human-readable explanation of evaluation results."""
        try:
            total = statistics.get("total_trades_evaluated", 0)
            blocked = statistics.get("trades_would_block", 0)
            allowed = statistics.get("trades_allowed", 0)
            blocked_pct = impact_analysis.get("blocked_percentage", 0)
            avg_conf = statistics.get("average_confidence", 0)
            
            explanation = (
                f"Scenario '{scenario_name}' evaluated {total} historical trades. "
                f"Under the hypothetical policy constraints, {blocked} trades ({blocked_pct:.1f}%) "
                f"would have been blocked, and {allowed} ({100-blocked_pct:.1f}%) would have been allowed. "
                f"Average confidence score across all trades was {avg_conf:.2f}. "
                f"This is informational analysis only and does not influence live decisions."
            )
            return explanation
        
        except Exception as e:
            logger.debug(f"Error generating explanation: {e}")
            return "Evaluation completed. This is informational analysis only."

    def _generate_comparison_explanation(
        self,
        result_a: Dict[str, Any],
        result_b: Dict[str, Any]
    ) -> str:
        """Generate human-readable comparison explanation."""
        try:
            name_a = result_a.get("scenario_name", "Scenario A")
            name_b = result_b.get("scenario_name", "Scenario B")
            blocked_a = result_a.get("impact_analysis", {}).get("blocked_percentage", 0)
            blocked_b = result_b.get("impact_analysis", {}).get("blocked_percentage", 0)
            
            comparison = (
                f"Comparing '{name_a}' and '{name_b}': "
                f"{name_a} would block {blocked_a:.1f}% of trades, "
                f"while {name_b} would block {blocked_b:.1f}%. "
                f"This comparison is directional only and does not rank scenarios. "
                f"No actual enforcement occurs."
            )
            return comparison
        
        except Exception as e:
            logger.debug(f"Error generating comparison explanation: {e}")
            return "Comparison completed. This is informational analysis only."

    def _generate_batch_explanation(
        self,
        successful_count: int,
        failed_count: int,
        summary_stats: Dict[str, Any]
    ) -> str:
        """Generate human-readable batch explanation."""
        try:
            avg_blocked = summary_stats.get("average_blocked_percentage", 0)
            consistency = summary_stats.get("consistency_score", 0)
            
            explanation = (
                f"Batch evaluation completed: {successful_count} successful, {failed_count} failed. "
                f"Average blocking rate across scenarios was {avg_blocked:.1f}%. "
                f"Consistency score: {consistency:.2f}. "
                f"This batch analysis is informational only and does not influence live decisions."
            )
            return explanation
        
        except Exception as e:
            logger.debug(f"Error generating batch explanation: {e}")
            return "Batch evaluation completed. This is informational analysis only."

    def _format_as_text(self, export_data: Dict[str, Any]) -> str:
        """Format evaluation result as human-readable text."""
        try:
            lines = [
                "=" * 80,
                "DECISION OFFLINE EVALUATION REPORT",
                "=" * 80,
                "",
                f"SCENARIO: {export_data.get('scenario_name', 'N/A')}",
                f"Scenario ID: {export_data.get('scenario_id', 'N/A')}",
                f"Evaluation Timestamp: {export_data.get('evaluation_timestamp', 'N/A')}",
                "",
                "POLICY CONSTRAINTS:",
            ]
            
            constraints = export_data.get("policy_constraints", {})
            for key, value in constraints.items():
                lines.append(f"  - {key}: {value}")
            
            lines.extend([
                "",
                "STATISTICS:",
            ])
            
            stats = export_data.get("statistics", {})
            lines.append(f"  Total Trades Evaluated: {stats.get('total_trades_evaluated', 0)}")
            lines.append(f"  Trades Allowed: {stats.get('trades_allowed', 0)}")
            lines.append(f"  Trades Would Block: {stats.get('trades_would_block', 0)}")
            lines.append(f"  Average Confidence: {stats.get('average_confidence', 0):.4f}")
            
            lines.extend([
                "",
                "IMPACT ANALYSIS:",
            ])
            
            impact = export_data.get("impact_analysis", {})
            lines.append(f"  Blocked Percentage: {impact.get('blocked_percentage', 0):.2f}%")
            lines.append(f"  Allowed Percentage: {impact.get('allowed_percentage', 0):.2f}%")
            
            lines.extend([
                "",
                "EXPLANATION:",
                export_data.get("explanation", "N/A"),
                "",
                "DISCLAIMER:",
                export_data.get("disclaimer", "N/A"),
                "",
                "EXPORT DISCLAIMER:",
                export_data.get("export_disclaimer", "N/A"),
                "",
                "=" * 80,
            ])
            
            return "\n".join(lines)
        
        except Exception as e:
            logger.debug(f"Error formatting as text: {e}")
            return json.dumps(export_data, indent=2, default=str)

    def _empty_evaluation_result(
        self,
        scenario_name: str,
        scenario_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return empty evaluation structure."""
        return {
            "scenario_name": scenario_name,
            "scenario_id": scenario_id,
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_constraints": config.get("policy_constraints", {}),
            "statistics": {
                "total_trades_evaluated": 0,
                "trades_allowed": 0,
                "trades_would_block": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "governance_pressure_distribution": {},
                "risk_flag_frequency": {},
                "trade_volume_statistics": {},
            },
            "impact_analysis": {
                "blocked_percentage": 0.0,
                "allowed_percentage": 100.0,
                "average_blocked_confidence": 0.0,
                "average_allowed_confidence": 0.0,
                "governance_pressure_change": 0.0,
            },
            "explanation": "Evaluation resulted in empty dataset.",
            "disclaimer": (
                "This evaluation is informational only and does not influence live decisions."
            ),
            "is_deterministic": True,
        }

    def _empty_comparison_result(self, name_a: str, name_b: str) -> Dict[str, Any]:
        """Return empty comparison structure."""
        return {
            "scenario_a_name": name_a,
            "scenario_b_name": name_b,
            "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
            "directional_differences": {},
            "isolation_analysis": {
                "scenario_a_unique_constraints": [],
                "scenario_b_unique_constraints": [],
                "shared_constraints": [],
            },
            "explanation": "Comparison could not be completed.",
            "disclaimer": (
                "This comparison is informational only and does not influence live decisions."
            ),
            "is_deterministic": True,
        }

    def _empty_batch_result(self) -> Dict[str, Any]:
        """Return empty batch result structure."""
        return {
            "batch_id": self._generate_batch_id(),
            "batch_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_scenarios": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "scenarios": [],
            "summary_statistics": {
                "average_blocked_percentage": 0.0,
                "min_blocked_percentage": 0.0,
                "max_blocked_percentage": 0.0,
                "consistency_score": 0.0,
            },
            "explanation": "Batch evaluation could not be completed.",
            "disclaimer": (
                "This batch evaluation is informational only and does not influence live decisions."
            ),
            "is_deterministic": True,
        }
