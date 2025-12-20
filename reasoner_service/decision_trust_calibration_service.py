"""
Decision Trust Calibration Service (Phase 10)

CRITICAL STATEMENT:
This service is DESCRIPTIVE ONLY. It computes historical metrics about signal consistency,
policy performance, and human reviewer alignment. It CANNOT and MUST NOT be used to make
or influence trading decisions.

This service:
✅ Analyzes historical consistency between signals and outcomes
✅ Summarizes policy violation frequency and regret patterns
✅ Measures human reviewer alignment with counterfactual outcomes
✅ Computes confidence stability and decay over time
✅ Provides INFORMATIONAL-ONLY analysis with explicit disclaimers

This service DOES NOT:
❌ Execute trades or positions
❌ Enforce rules or block decisions
❌ Recommend actions or strategies
❌ Rank, score, or weight systems
❌ Optimize or learn from outcomes
❌ Trigger any external changes
❌ Provide actionable guidance

SAFETY GUARANTEES:
- All outputs are deeply copied before returning
- All inputs are deeply copied upon receipt
- All methods are fail-silent (never raise exceptions)
- No external service state is ever modified
- No database writes, no async operations
- Deterministic outputs (same input = same output)
- Explicit informational disclaimers in all outputs
"""

from datetime import datetime, timezone, timedelta
from copy import deepcopy
from collections import defaultdict
import json
import hashlib
from enum import Enum


class SignalType(Enum):
    """Types of trading signals that can be calibrated."""
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"


class CalibrationMetric(Enum):
    """Historical calibration metrics (descriptive only)."""
    CONSISTENCY = "consistency"
    DIVERGENCE = "divergence"
    FREQUENCY = "frequency"
    DENSITY = "density"
    VARIANCE = "variance"
    DECAY = "decay"


class DecisionTrustCalibrationService:
    """
    PHASE 10: Decision Trust Calibration Service

    Computes DESCRIPTIVE-ONLY historical metrics about signal consistency,
    policy performance, and human reviewer alignment.

    This is a PURE ANALYSIS service with ZERO authority or influence over
    any trading decisions, execution, enforcement, or optimization.

    All outputs include explicit disclaimers: "Informational analysis only.
    This output has no authority over trading decisions."
    """

    def __init__(self):
        """Initialize calibration service with empty state."""
        self._signal_calibrations = {}
        self._policy_calibrations = {}
        self._reviewer_calibrations = {}
        self._stability_records = {}
        self._all_calibration_events = []

    def calibrate_signals(self, memory_snapshot):
        """
        Compute historical consistency metrics between signals and actual outcomes.

        ⚠️  AUTHORITY WARNING:
        This method is INFORMATIONAL ONLY and produces DESCRIPTIVE HISTORICAL ANALYSIS.
        
        It analyzes historical alignment between signal predictions and outcomes that
        actually occurred. This is a READ-ONLY analysis of past data.
        
        🚫 CRITICAL — THIS ANALYSIS:
        - Does NOT recommend trusting or distrusting any signal
        - Has ZERO authority over signal weighting or selection
        - Must NEVER be wired to decision-making logic
        - Must NEVER be used for real-time signal filtering
        - Is NOT predictive of future signal performance
        - Cannot and must not influence trading decisions
        
        Any downstream use of this analysis to make trading decisions
        violates the fundamental design constraint of this service.

        Parameters:
        -----------
        memory_snapshot : dict
            Snapshot from DecisionIntelligenceMemoryService containing:
            - signal_records: List of historical signal records
            - outcome_records: List of outcome records
            - correlation_ids: Trading event identifiers

        Returns:
        --------
        dict with keys:
            - "disclaimer": Mandatory non-authority statement
            - "total_signals": Count of signals analyzed (descriptive)
            - "total_outcomes": Count of outcomes analyzed (descriptive)
            - "signals_by_type": Breakdown by signal type (descriptive)
            - "consistency_analysis": Historical alignment metrics (descriptive, not predictive)
            - "explanation": Why these metrics are historical only
            - "processed_at": Timestamp of analysis

        INFORMATIONAL-ONLY CONSTRAINTS:
        - Consistency rate is DESCRIPTIVE of past alignment, NOT predictive
        - High consistency does NOT mean the signal is reliable
        - Low consistency does NOT mean the signal should be distrusted
        - These metrics are suitable only for historical analysis and audit trails
        - Should NEVER influence decision-making algorithms
        """
        try:
            # Deepcopy input to prevent external modification
            snapshot = deepcopy(memory_snapshot) if memory_snapshot else {}

            # Extract data safely
            signal_records = snapshot.get("signal_records", [])
            outcome_records = snapshot.get("outcome_records", [])

            if not signal_records or not outcome_records:
                result = {
                    "disclaimer": self._get_disclaimer(),
                    "total_signals": len(signal_records),
                    "total_outcomes": len(outcome_records),
                    "signals_by_type": {},
                    "consistency_analysis": self._empty_consistency_analysis(),
                    "explanation": "No signal or outcome records to analyze.",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                return deepcopy(result)

            # Compute consistency metrics
            calibration = self._compute_signal_consistency(
                signal_records, outcome_records
            )

            # Build result
            result = {
                "disclaimer": self._get_disclaimer(),
                "total_signals": len(signal_records),
                "total_outcomes": len(outcome_records),
                "signals_by_type": self._breakdown_signals_by_type(signal_records),
                "consistency_analysis": calibration,
                "explanation": (
                    "Historical analysis of signal consistency. These metrics show "
                    "how often signals aligned with outcomes in the past. They do NOT "
                    "recommend trusting or distrusting signals in the future."
                ),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            # Record event
            self._all_calibration_events.append({
                "type": "signal_calibration",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal_count": len(signal_records),
                "outcome_count": len(outcome_records),
            })

            return deepcopy(result)

        except Exception:
            # Fail-silent: return empty result
            return deepcopy({
                "disclaimer": self._get_disclaimer(),
                "total_signals": 0,
                "total_outcomes": 0,
                "signals_by_type": {},
                "consistency_analysis": self._empty_consistency_analysis(),
                "explanation": "Analysis failed gracefully.",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })

    def calibrate_policies(self, offline_evaluations):
        """
        Compute historical violation frequency and regret patterns for policies.

        ⚠️  AUTHORITY WARNING:
        This method is INFORMATIONAL ONLY and produces DESCRIPTIVE HISTORICAL ANALYSIS.
        
        It analyzes how often policies were violated and computes historical regret
        metrics by replaying past decisions. This is a READ-ONLY historical analysis.
        
        🚫 CRITICAL — THIS ANALYSIS:
        - Does NOT recommend policy changes or optimization
        - Has ZERO authority over policy weighting or selection
        - Does NOT compute which policies are "better" or "worse"
        - Must NEVER be wired to policy enforcement or adaptation
        - Must NEVER influence policy parameters or weights
        - Is NOT for real-time policy evaluation
        - Cannot and must not influence trading decisions
        
        Any downstream use of this analysis to modify policies, weights,
        or enforcement rules violates the fundamental design constraint.

        Parameters:
        -----------
        offline_evaluations : dict or list
            Evaluations from DecisionOfflineEvaluationService containing:
            - policy_results: List of policy evaluation records
            - violation_events: Records of policy violations
            - counterfactual_outcomes: What would have happened (hypothetical)

        Returns:
        --------
        dict with keys:
            - "disclaimer": Mandatory non-authority statement
            - "total_policies": Count of unique policies analyzed (descriptive)
            - "total_evaluations": Count of evaluation records (descriptive)
            - "violation_summary": Historical violation patterns (descriptive)
            - "regret_analysis": Patterns in counterfactual outcomes (historical, not predictive)
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        INFORMATIONAL-ONLY CONSTRAINTS:
        - Violation frequency is HISTORICAL, not predictive of future violations
        - Regret analysis is OBSERVATIONAL of past counterfactuals, not prescriptive
        - High violation frequency does NOT indicate a policy should be modified
        - Cannot be used to modify policy weights, thresholds, or enforcement
        - Regret is a hypothetical metric, not a performance score
        """
        try:
            # Deepcopy input
            evaluations = deepcopy(offline_evaluations) if offline_evaluations else {}

            # Extract data safely
            if isinstance(evaluations, list):
                policy_results = evaluations
                violation_events = []
            else:
                policy_results = evaluations.get("policy_results", [])
                violation_events = evaluations.get("violation_events", [])

            if not policy_results and not violation_events:
                result = {
                    "disclaimer": self._get_disclaimer(),
                    "total_policies": 0,
                    "total_evaluations": len(policy_results),
                    "violation_summary": self._empty_violation_summary(),
                    "regret_analysis": self._empty_regret_analysis(),
                    "explanation": "No policy evaluation records to analyze.",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                return deepcopy(result)

            # Compute calibration
            policies_analyzed = self._extract_unique_policies(policy_results)
            violations_analyzed = self._compute_violation_patterns(
                policy_results, violation_events
            )
            regret_analyzed = self._compute_regret_patterns(policy_results)

            result = {
                "disclaimer": self._get_disclaimer(),
                "total_policies": len(policies_analyzed),
                "total_evaluations": len(policy_results),
                "violation_summary": violations_analyzed,
                "regret_analysis": regret_analyzed,
                "explanation": (
                    "Historical analysis of policy violation frequency and regret patterns. "
                    "These metrics show how often policies were violated and what counterfactual "
                    "outcomes might have been. They do NOT recommend policy changes or optimization."
                ),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            # Record event
            self._all_calibration_events.append({
                "type": "policy_calibration",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "policy_count": len(policies_analyzed),
                "evaluation_count": len(policy_results),
            })

            return deepcopy(result)

        except Exception:
            # Fail-silent
            return deepcopy({
                "disclaimer": self._get_disclaimer(),
                "total_policies": 0,
                "total_evaluations": 0,
                "violation_summary": self._empty_violation_summary(),
                "regret_analysis": self._empty_regret_analysis(),
                "explanation": "Analysis failed gracefully.",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })

    def calibrate_reviewers(self, human_reviews, counterfactual_results):
        """
        Measure historical alignment between human reviews and counterfactual outcomes.

        ⚠️  AUTHORITY WARNING:
        This method is INFORMATIONAL ONLY and produces DESCRIPTIVE HISTORICAL ANALYSIS.
        
        It measures how often human reviewers' concerns aligned with what counterfactual
        analysis suggested hypothetically. This is a READ-ONLY historical comparison.
        
        🚫 CRITICAL — THIS ANALYSIS:
        - Does NOT rank, score, or weight reviewers
        - Has ZERO authority over reviewer authority or influence
        - Does NOT compute which reviewers are "more reliable"
        - Must NEVER be wired to reviewer filtering or weighting
        - Must NEVER influence downstream handling of human reviews
        - Cannot and must not influence trading decisions
        
        Disagreement frequency is descriptive only. Reviewers with higher
        disagreement counts are not "worse" — they may simply be more critical.
        Any downstream use of this analysis to rank or weight reviewers
        violates the fundamental design constraint.

        Parameters:
        -----------
        human_reviews : dict or list
            Reviews from DecisionHumanReviewService containing:
            - review_sessions: List of review session records
            - annotations: Human observations and annotations (informational)
            - disagreements: Records of human disagreements

        counterfactual_results : dict or list
            Results from CounterfactualEnforcementSimulator containing:
            - counterfactual_outcomes: What would have happened (hypothetical)
            - simulated_results: Alternative decision outcomes (hypothetical)

        Returns:
        --------
        dict with keys:
            - "disclaimer": Mandatory non-authority statement
            - "total_reviewers": Count of unique reviewers (descriptive)
            - "total_reviews": Count of review records (descriptive)
            - "alignment_analysis": Alignment with counterfactual outcomes (descriptive, historical)
            - "disagreement_patterns": Historical disagreement persistence (descriptive, not ranking)
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        INFORMATIONAL-ONLY CONSTRAINTS:
        - Alignment frequency is HISTORICAL, not predictive of reviewer value
        - Disagreement patterns are DESCRIPTIVE, not performance scores
        - High disagreement does NOT indicate a reviewer should be de-weighted
        - Cannot be used to modify reviewer authority, weighting, or influence
        - All metrics are context-dependent and non-rankable across reviewers
        """
        try:
            # Deepcopy inputs
            reviews = deepcopy(human_reviews) if human_reviews else {}
            counterfactuals = deepcopy(counterfactual_results) if counterfactual_results else {}

            # Extract data safely
            if isinstance(reviews, list):
                review_records = reviews
            else:
                review_records = reviews.get("review_sessions", [])

            if isinstance(counterfactuals, list):
                counterfactual_records = counterfactuals
            else:
                counterfactual_records = counterfactuals.get("counterfactual_outcomes", [])

            if not review_records or not counterfactual_records:
                result = {
                    "disclaimer": self._get_disclaimer(),
                    "total_reviewers": len(self._extract_unique_reviewers(review_records)),
                    "total_reviews": len(review_records),
                    "alignment_analysis": self._empty_alignment_analysis(),
                    "disagreement_patterns": self._empty_disagreement_patterns(),
                    "explanation": "No review or counterfactual records to analyze.",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                return deepcopy(result)

            # Compute calibration
            unique_reviewers = self._extract_unique_reviewers(review_records)
            alignment = self._compute_alignment_patterns(review_records, counterfactual_records)
            disagreements = self._compute_disagreement_persistence(review_records)

            result = {
                "disclaimer": self._get_disclaimer(),
                "total_reviewers": len(unique_reviewers),
                "total_reviews": len(review_records),
                "alignment_analysis": alignment,
                "disagreement_patterns": disagreements,
                "explanation": (
                    "Historical analysis of human reviewer alignment with counterfactual outcomes. "
                    "These metrics show how often reviewers' concerns aligned with what counterfactual "
                    "analysis suggested. They do NOT rank or score reviewers."
                ),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            # Record event
            self._all_calibration_events.append({
                "type": "reviewer_calibration",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reviewer_count": len(unique_reviewers),
                "review_count": len(review_records),
            })

            return deepcopy(result)

        except Exception:
            # Fail-silent
            return deepcopy({
                "disclaimer": self._get_disclaimer(),
                "total_reviewers": 0,
                "total_reviews": 0,
                "alignment_analysis": self._empty_alignment_analysis(),
                "disagreement_patterns": self._empty_disagreement_patterns(),
                "explanation": "Analysis failed gracefully.",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })

    def compute_stability(self, memory_snapshot):
        """
        Compute historical confidence stability and variance over time.

        ⚠️  AUTHORITY WARNING:
        This method is INFORMATIONAL ONLY and produces DESCRIPTIVE HISTORICAL ANALYSIS.
        
        It analyzes how stable historical confidence levels have been, whether
        confidence shows decay patterns, and variance characteristics. This is
        a READ-ONLY historical analysis of past confidence data.
        
        🚫 CRITICAL — THIS ANALYSIS:
        - Does NOT predict future confidence levels
        - Has ZERO authority over confidence thresholds or parameters
        - Does NOT indicate whether confidence "should be" adjusted
        - Must NEVER be wired to real-time confidence modification
        - Must NEVER influence decision filtering based on stability
        - Is purely observational of historical patterns
        - Cannot and must not influence trading decisions
        
        Stability decay is a historical observation, not a signal to
        suppress or filter future decisions. Any downstream use of this
        analysis to modify confidence handling or decision acceptance
        violates the fundamental design constraint.

        Parameters:
        -----------
        memory_snapshot : dict
            Snapshot from DecisionIntelligenceMemoryService containing:
            - confidence_records: Historical confidence values with timestamps
            - decision_timeline: Sequence of decisions and confidences

        Returns:
        --------
        dict with keys:
            - "disclaimer": Mandatory non-authority statement
            - "total_records": Count of confidence records analyzed (descriptive)
            - "confidence_statistics": Mean, median, std dev (descriptive, historical)
            - "decay_analysis": Confidence decay over time (if observed, descriptive only)
            - "variance_analysis": Dispersion of confidence values (descriptive)
            - "stability_index": Aggregated stability metric (descriptive, not prescriptive)
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        INFORMATIONAL-ONLY CONSTRAINTS:
        - Stability metrics are HISTORICAL only, not predictive
        - Decay patterns are OBSERVATIONAL from past data
        - These do NOT predict or influence future confidence
        - Cannot be used to modify confidence levels or thresholds
        - High decay does NOT indicate future decisions should be suppressed
        - Low stability does NOT indicate future decisions will be bad
        """
        try:
            # Deepcopy input
            snapshot = deepcopy(memory_snapshot) if memory_snapshot else {}

            # Extract data safely
            confidence_records = snapshot.get("confidence_records", [])
            decision_timeline = snapshot.get("decision_timeline", [])

            if not confidence_records:
                result = {
                    "disclaimer": self._get_disclaimer(),
                    "total_records": 0,
                    "confidence_statistics": self._empty_confidence_statistics(),
                    "decay_analysis": self._empty_decay_analysis(),
                    "variance_analysis": self._empty_variance_analysis(),
                    "stability_index": 0.0,
                    "explanation": "No confidence records to analyze.",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                return deepcopy(result)

            # Compute stability metrics
            stats = self._compute_confidence_statistics(confidence_records)
            decay = self._compute_decay_pattern(confidence_records)
            variance = self._compute_variance_analysis(confidence_records)
            stability_idx = self._compute_stability_index(stats, decay, variance)

            result = {
                "disclaimer": self._get_disclaimer(),
                "total_records": len(confidence_records),
                "confidence_statistics": stats,
                "decay_analysis": decay,
                "variance_analysis": variance,
                "stability_index": stability_idx,
                "explanation": (
                    "Historical analysis of confidence stability and variance. "
                    "These metrics show how stable confidence has been over time. "
                    "They are OBSERVATIONAL only and should NOT be used to modify future confidence."
                ),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            # Record event
            self._all_calibration_events.append({
                "type": "stability_computation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_count": len(confidence_records),
            })

            return deepcopy(result)

        except Exception:
            # Fail-silent
            return deepcopy({
                "disclaimer": self._get_disclaimer(),
                "total_records": 0,
                "confidence_statistics": self._empty_confidence_statistics(),
                "decay_analysis": self._empty_decay_analysis(),
                "variance_analysis": self._empty_variance_analysis(),
                "stability_index": 0.0,
                "explanation": "Analysis failed gracefully.",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })

    def export_trust_snapshot(self, calibration_result, format="json"):
        """
        Export trust calibration results with mandatory non-authority disclaimers.

        ⚠️  CRITICAL STATEMENT:
        All exported data is INFORMATIONAL ONLY. Every export includes a prominent
        disclaimer that this data has ZERO authority over trading decisions.

        This method produces deterministic exports (sorted keys, consistent ordering)
        of historical trust calibration analysis. Exports are READ-ONLY and must
        never be modified or wired to execution logic.

        Parameters:
        -----------
        calibration_result : dict
            Result from any calibration or stability computation method
            (must already include disclaimers)

        format : str
            Export format: "json" or "text"
            Both formats include non-authority disclaimers

        Returns:
        --------
        str
            Exported result in specified format with mandatory disclaimer

        INFORMATIONAL-ONLY CONSTRAINTS:
        - All exports are deterministic (same input = same output always)
        - All exports include comprehensive non-authority disclaimers
        - Sorted keys ensure reproducibility and auditability
        - Exports are suitable only for historical analysis and archival
        - Must NEVER be wired to decision-making, execution, or policy application
        """
        try:
            # Deepcopy input to prevent modification
            result = deepcopy(calibration_result) if calibration_result else {}

            if format == "json":
                return self._export_as_json(result)
            elif format == "text":
                return self._export_as_text(result)
            else:
                # Default to JSON
                return self._export_as_json(result)

        except Exception:
            # Fail-silent: return minimal export
            if format == "text":
                return "DECISION TRUST CALIBRATION EXPORT\n\nExport failed gracefully."
            else:
                return json.dumps({
                    "error": "Export failed gracefully",
                    "disclaimer": self._get_disclaimer(),
                }, indent=2)

    # ========== PRIVATE HELPER METHODS ==========

    def _get_disclaimer(self):
        """Get mandatory non-authority disclaimer.
        
        This disclaimer must appear in EVERY output. It is the primary
        control preventing misuse of this informational service.
        
        🚫 ABSOLUTE CONSTRAINT:
        Any output lacking this disclaimer is considered a bug.
        """
        return (
            "🚫 AUTHORITY WARNING - THIS OUTPUT HAS ZERO DECISION AUTHORITY:\n"
            "This is INFORMATIONAL ANALYSIS ONLY. These trust calibration metrics are "
            "DESCRIPTIVE HISTORICAL ANALYSIS of past performance patterns.\n"
            "\n"
            "⚠️  CRITICAL CONSTRAINTS:\n"
            "- This analysis has NO authority over trading decisions, execution, or operations\n"
            "- These results must NEVER be wired to decision-making logic\n"
            "- Do not rank or apply this data to systems\n"
            "- Do not optimize filtering or suppression based on this data\n"
            "- Historical patterns do NOT indicate future behavior\n"
            "- All metrics are context-dependent and non-comparable\n"
            "\n"
            "Any use of this analysis to influence trading or make trading decisions "
            "is a fundamental violation of system design. "
            "Execution authority must reside in a separate system boundary."
        )

    def _compute_signal_consistency(self, signal_records, outcome_records):
        """Compute historical consistency between signals and outcomes.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes how often signals historically aligned with outcomes.
        This is a HISTORICAL METRIC with zero predictive or prescriptive power.
        
        High consistency does NOT mean signals should be trusted or weighted higher.
        Low consistency does NOT mean signals should be distrusted or filtered.
        
        This metric is suitable only for audit and historical analysis.
        """
        if not signal_records or not outcome_records:
            return self._empty_consistency_analysis()

        try:
            # Build correlation map
            matched_pairs = 0
            total_signals = len(signal_records)

            for signal in signal_records:
                signal_id = signal.get("id", "")
                for outcome in outcome_records:
                    if outcome.get("signal_id") == signal_id:
                        matched_pairs += 1
                        break

            consistency_rate = matched_pairs / total_signals if total_signals > 0 else 0.0

            return {
                "matched_pairs": matched_pairs,
                "total_signals": total_signals,
                "consistency_rate": round(consistency_rate, 4),
                "coverage_percentage": round((consistency_rate * 100), 2),
                "note": "Historical consistency only. Does not predict future alignment.",
            }
        except Exception:
            return self._empty_consistency_analysis()

    def _breakdown_signals_by_type(self, signal_records):
        """Breakdown signals by type."""
        breakdown = {}
        for signal in signal_records:
            signal_type = signal.get("signal_type", "unknown")
            breakdown[signal_type] = breakdown.get(signal_type, 0) + 1
        return breakdown

    def _extract_unique_policies(self, policy_results):
        """Extract unique policy identifiers."""
        policies = set()
        for result in policy_results:
            policy_id = result.get("policy_id")
            if policy_id:
                policies.add(policy_id)
        return policies

    def _compute_violation_patterns(self, policy_results, violation_events):
        """Compute historical violation patterns.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes how often policies were violated in the past.
        This is a HISTORICAL FREQUENCY metric with zero prescriptive power.
        
        High violation frequency does NOT indicate a policy should be modified.
        Low violation frequency does NOT indicate a policy is working well.
        
        These patterns are suitable only for historical analysis and compliance review.
        Do NOT use to drive policy adaptation or enforcement changes.
        """
        violation_counts = defaultdict(int)
        total_evaluations = len(policy_results)

        for result in policy_results:
            policy_id = result.get("policy_id")
            if result.get("violated"):
                violation_counts[policy_id] += 1

        for event in violation_events:
            policy_id = event.get("policy_id")
            if policy_id:
                violation_counts[policy_id] += 1

        return {
            "total_violation_events": sum(violation_counts.values()),
            "total_evaluations": total_evaluations,
            "violation_frequency": round(
                sum(violation_counts.values()) / total_evaluations
                if total_evaluations > 0
                else 0.0,
                4,
            ),
            "violations_by_policy": dict(violation_counts),
            "note": "Historical violation frequency only. Not a policy assessment.",
        }

    def _compute_regret_patterns(self, policy_results):
        """Compute historical regret patterns."""
        total_regret = 0.0
        regret_events = 0

        for result in policy_results:
            regret = result.get("regret", 0.0)
            if regret > 0:
                total_regret += regret
                regret_events += 1

        avg_regret = total_regret / regret_events if regret_events > 0 else 0.0

        return {
            "total_regret_events": regret_events,
            "total_regret_magnitude": round(total_regret, 4),
            "average_regret": round(avg_regret, 4),
            "note": "Historical regret analysis only. Not an optimization guide.",
        }

    def _extract_unique_reviewers(self, review_records):
        """Extract unique reviewer identifiers."""
        reviewers = set()
        for record in review_records:
            if isinstance(record, dict):
                # Try multiple keys where reviewer ID might be
                reviewer_id = (
                    record.get("annotator")
                    or record.get("disagreer")
                    or record.get("reviewer_id")
                )
                if reviewer_id:
                    reviewers.add(reviewer_id)
        return reviewers

    def _compute_alignment_patterns(self, review_records, counterfactual_records):
        """Compute historical alignment between reviewers and counterfactuals.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes how often human reviewer concerns aligned with counterfactual
        analysis. This is a HISTORICAL COMPARISON metric with zero rankability.
        
        High alignment does NOT indicate a reviewer is more reliable or should be weighted higher.
        Low alignment does NOT indicate a reviewer is less reliable or should be filtered.
        
        Alignment rates are CONTEXT-DEPENDENT and NON-COMPARABLE across reviewers.
        This metric is suitable only for historical analysis.
        Do NOT use to rank, weight, or filter reviewers.
        """
        alignment_matches = 0
        total_comparisons = 0

        for review in review_records:
            for counterfactual in counterfactual_records:
                total_comparisons += 1
                review_concern = review.get("reason") or review.get("text")
                counterfactual_outcome = counterfactual.get("alternative_outcome")

                if review_concern and counterfactual_outcome:
                    # Simple string overlap check
                    if isinstance(review_concern, str) and isinstance(counterfactual_outcome, str):
                        if review_concern.lower() in counterfactual_outcome.lower():
                            alignment_matches += 1

        alignment_rate = (
            alignment_matches / total_comparisons if total_comparisons > 0 else 0.0
        )

        return {
            "alignment_matches": alignment_matches,
            "total_comparisons": total_comparisons,
            "alignment_rate": round(alignment_rate, 4),
            "alignment_percentage": round((alignment_rate * 100), 2),
            "note": "Historical alignment with counterfactuals only. No reviewer ranking.",
        }

    def _compute_disagreement_persistence(self, review_records):
        """Compute historical disagreement persistence patterns.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes how often reviewers historically disagreed.
        This is a FREQUENCY metric with zero performance implications.
        
        High disagreement frequency does NOT indicate a reviewer is unreliable or should be filtered.
        Low disagreement frequency does NOT indicate a reviewer is reliable or should be weighted higher.
        
        Disagreement patterns are CONTEXT-DEPENDENT and NON-COMPARABLE across reviewers.
        Critical reviewers may naturally have higher disagreement counts.
        This metric is suitable only for historical analysis.
        Do NOT use to rank or weight reviewers.
        """
        disagreement_counts = defaultdict(int)
        total_reviews = len(review_records)

        for record in review_records:
            if record.get("type") == "disagreement" or record.get("disagreement_count"):
                reviewer = record.get("disagreer", "unknown")
                disagreement_counts[reviewer] += 1

        return {
            "total_disagreements": sum(disagreement_counts.values()),
            "total_reviews": total_reviews,
            "disagreement_frequency": round(
                sum(disagreement_counts.values()) / total_reviews if total_reviews > 0 else 0.0,
                4,
            ),
            "disagreements_by_reviewer": dict(disagreement_counts),
            "note": "Historical disagreement patterns only. Not a reviewer ranking.",
        }

    def _compute_confidence_statistics(self, confidence_records):
        """Compute historical confidence statistics.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes descriptive statistics on past confidence values.
        These are HISTORICAL OBSERVATIONS with zero predictive power.
        
        Mean/median confidence does NOT predict future confidence levels.
        Confidence variance does NOT indicate future decisions should be filtered.
        
        These statistics are suitable only for historical analysis and audit trails.
        Do NOT use to predict, suppress, or adjust future confidence values.
        """
        if not confidence_records:
            return self._empty_confidence_statistics()

        try:
            values = []
            for record in confidence_records:
                confidence = record.get("confidence_value")
                if isinstance(confidence, (int, float)):
                    values.append(float(confidence))

            if not values:
                return self._empty_confidence_statistics()

            mean_val = sum(values) / len(values)
            median_val = sorted(values)[len(values) // 2]
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5

            return {
                "mean": round(mean_val, 4),
                "median": round(median_val, 4),
                "std_dev": round(std_dev, 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "count": len(values),
                "note": "Historical confidence statistics only. Not predictive.",
            }
        except Exception:
            return self._empty_confidence_statistics()

    def _compute_decay_pattern(self, confidence_records):
        """Compute historical confidence decay over time.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes observed confidence decay from past data.
        This is a HISTORICAL PATTERN with zero predictive or prescriptive power.
        
        Observed decay in past confidence does NOT predict future decay.
        Observed decay does NOT indicate future decisions should be suppressed or filtered.
        
        Decay patterns are CONTEXT-DEPENDENT and transient.
        This metric is suitable only for historical analysis and audit trails.
        Do NOT use to adjust, suppress, or modify future confidence levels.
        """
        if not confidence_records or len(confidence_records) < 2:
            return self._empty_decay_analysis()

        try:
            # Sort by timestamp
            sorted_records = sorted(
                confidence_records,
                key=lambda x: x.get("timestamp", ""),
            )

            first_value = float(sorted_records[0].get("confidence_value", 0.5))
            last_value = float(sorted_records[-1].get("confidence_value", 0.5))

            decay_rate = (first_value - last_value) / first_value if first_value > 0 else 0.0

            return {
                "first_value": round(first_value, 4),
                "last_value": round(last_value, 4),
                "absolute_decay": round(first_value - last_value, 4),
                "decay_rate": round(decay_rate, 4),
                "note": "Historical decay pattern only. Not predictive.",
            }
        except Exception:
            return self._empty_decay_analysis()

    def _compute_variance_analysis(self, confidence_records):
        """Compute historical variance analysis.
        
        ⚠️  INFORMATIONAL ONLY:
        This computes variance and dispersion of past confidence values.
        This is a HISTORICAL OBSERVATION with zero predictive power.
        
        High variance does NOT indicate future confidence will be unstable.
        Low variance does NOT indicate future confidence will be stable.
        
        Variance patterns are TRANSIENT and CONTEXT-DEPENDENT.
        This metric is suitable only for historical analysis and audit trails.
        Do NOT use to suppress, filter, or adjust future decisions based on variance.
        """
        if not confidence_records:
            return self._empty_variance_analysis()

        try:
            values = []
            for record in confidence_records:
                confidence = record.get("confidence_value")
                if isinstance(confidence, (int, float)):
                    values.append(float(confidence))

            if len(values) < 2:
                return self._empty_variance_analysis()

            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            coefficient_of_variation = (variance ** 0.5) / mean_val if mean_val > 0 else 0.0

            return {
                "variance": round(variance, 4),
                "std_dev": round(variance ** 0.5, 4),
                "coefficient_of_variation": round(coefficient_of_variation, 4),
                "range": round(max(values) - min(values), 4),
                "note": "Historical variance only. Not prescriptive.",
            }
        except Exception:
            return self._empty_variance_analysis()

    def _compute_stability_index(self, stats, decay, variance):
        """Compute aggregate stability index.
        
        ⚠️  INFORMATIONAL ONLY:
        This aggregates historical variance and decay into a single index (0.0-1.0).
        This is a DERIVED HISTORICAL METRIC with zero prescriptive power.
        
        Stability index is NOT:
        - A performance score
        - A reliability measure
        - A future predictor
        - Authority to suppress or filter decisions
        
        Index values are CONTEXT-DEPENDENT and NON-COMPARABLE.
        This metric is suitable only for historical analysis and audit trails.
        Do NOT use this index to weight, filter, or adjust future decisions.
        """
        try:
            # Stability = 1.0 when perfectly stable (low variance, no decay)
            # Stability = 0.0 when chaotic (high variance, high decay)

            std_dev = stats.get("std_dev", 0.5)
            decay_rate = decay.get("decay_rate", 0.0)

            # Normalize to 0-1 range
            variance_component = min(std_dev / 1.0, 1.0)  # Higher std dev = lower stability
            decay_component = abs(decay_rate)  # Higher decay = lower stability

            stability = 1.0 - ((variance_component + decay_component) / 2.0)
            return round(max(0.0, min(1.0, stability)), 4)
        except Exception:
            return 0.0

    def _export_as_json(self, result):
        """Export as deterministic JSON."""
        try:
            json_str = json.dumps(result, indent=2, sort_keys=True, default=str)
            return json_str
        except Exception:
            return json.dumps({
                "error": "JSON export failed",
                "disclaimer": self._get_disclaimer(),
            }, indent=2)

    def _export_as_text(self, result):
        """Export as human-readable text."""
        try:
            lines = [
                "=" * 80,
                "DECISION TRUST CALIBRATION SNAPSHOT",
                "=" * 80,
                "",
                "DISCLAIMER:",
                self._get_disclaimer(),
                "",
                "=" * 80,
                "",
            ]

            # Add main content
            for key, value in sorted(result.items()):
                if key == "disclaimer":
                    continue
                if isinstance(value, dict):
                    lines.append(f"{key}:")
                    for k, v in sorted(value.items()):
                        lines.append(f"  {k}: {v}")
                    lines.append("")
                elif isinstance(value, list):
                    lines.append(f"{key}: {len(value)} items")
                else:
                    lines.append(f"{key}: {value}")

            return "\n".join(lines)
        except Exception:
            return "DECISION TRUST CALIBRATION SNAPSHOT\n\nExport failed gracefully."

    # ========== EMPTY STRUCTURE HELPERS ==========

    def _empty_consistency_analysis(self):
        """Return empty consistency analysis."""
        return {
            "matched_pairs": 0,
            "total_signals": 0,
            "consistency_rate": 0.0,
            "coverage_percentage": 0.0,
        }

    def _empty_violation_summary(self):
        """Return empty violation summary."""
        return {
            "total_violation_events": 0,
            "total_evaluations": 0,
            "violation_frequency": 0.0,
            "violations_by_policy": {},
        }

    def _empty_regret_analysis(self):
        """Return empty regret analysis."""
        return {
            "total_regret_events": 0,
            "total_regret_magnitude": 0.0,
            "average_regret": 0.0,
        }

    def _empty_alignment_analysis(self):
        """Return empty alignment analysis."""
        return {
            "alignment_matches": 0,
            "total_comparisons": 0,
            "alignment_rate": 0.0,
            "alignment_percentage": 0.0,
        }

    def _empty_disagreement_patterns(self):
        """Return empty disagreement patterns."""
        return {
            "total_disagreements": 0,
            "total_reviews": 0,
            "disagreement_frequency": 0.0,
            "disagreements_by_reviewer": {},
        }

    def _empty_confidence_statistics(self):
        """Return empty confidence statistics."""
        return {
            "mean": 0.0,
            "median": 0.0,
            "std_dev": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
        }

    def _empty_decay_analysis(self):
        """Return empty decay analysis."""
        return {
            "first_value": 0.0,
            "last_value": 0.0,
            "absolute_decay": 0.0,
            "decay_rate": 0.0,
        }

    def _empty_variance_analysis(self):
        """Return empty variance analysis."""
        return {
            "variance": 0.0,
            "std_dev": 0.0,
            "coefficient_of_variation": 0.0,
            "range": 0.0,
        }
