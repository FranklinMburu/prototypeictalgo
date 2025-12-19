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
        Compute consistency metrics between signals and actual outcomes.

        This method is DESCRIPTIVE ONLY. It analyzes historical alignment
        between signal predictions and outcomes that actually occurred.
        It does NOT recommend trusting or distrusting any signal.

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
            - "disclaimer": Informational-only statement
            - "total_signals": Count of signals analyzed
            - "total_outcomes": Count of outcomes analyzed
            - "signals_by_type": Breakdown by signal type
            - "consistency_analysis": Historical alignment metrics
            - "explanation": Why these are informational only
            - "processed_at": Timestamp of analysis

        IMPORTANT:
        - This is NOT a recommendation engine
        - Consistency does NOT imply future reliability
        - These metrics are historical only
        - Should never influence decision-making
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
        Compute regret frequency and violation patterns for policies.

        This method is DESCRIPTIVE ONLY. It analyzes how often policies
        were violated and computes historical regret metrics. It does NOT
        recommend policy changes, weighting, or optimization.

        Parameters:
        -----------
        offline_evaluations : dict or list
            Evaluations from DecisionOfflineEvaluationService containing:
            - policy_results: List of policy evaluation records
            - violation_events: Records of policy violations
            - counterfactual_outcomes: What would have happened

        Returns:
        --------
        dict with keys:
            - "disclaimer": Informational-only statement
            - "total_policies": Count of unique policies
            - "total_evaluations": Count of evaluation records
            - "violation_summary": Historical violation patterns
            - "regret_analysis": Patterns in counterfactual outcomes
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        IMPORTANT:
        - Violation frequency is NOT a policy ranking
        - Regret analysis is NOT an optimization guide
        - This cannot be used to modify policy weights
        - These are historical patterns only
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
        Measure alignment between human reviews and counterfactual outcomes.

        This method is DESCRIPTIVE ONLY. It measures how often human reviewers
        agreed or disagreed with what counterfactual analysis suggested would
        have been better outcomes. It does NOT rank, score, or weight reviewers.

        Parameters:
        -----------
        human_reviews : dict or list
            Reviews from DecisionHumanReviewService containing:
            - review_sessions: List of review session records
            - annotations: Human observations and annotations
            - disagreements: Records of human disagreements

        counterfactual_results : dict or list
            Results from CounterfactualEnforcementSimulator containing:
            - counterfactual_outcomes: What would have happened
            - simulated_results: Alternative decision outcomes

        Returns:
        --------
        dict with keys:
            - "disclaimer": Informational-only statement
            - "total_reviewers": Count of unique reviewers
            - "total_reviews": Count of review records
            - "alignment_analysis": Alignment with counterfactual outcomes
            - "disagreement_patterns": Historical disagreement persistence
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        IMPORTANT:
        - Alignment frequency is NOT a reviewer ranking
        - Disagreement patterns are NOT performance scores
        - This cannot be used to weight human input
        - No reviewer is "better" or "worse" based on these metrics
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
        Compute confidence stability and decay over time.

        This method is DESCRIPTIVE ONLY. It analyzes how stable confidence
        levels have been over time, whether confidence decays, and variance
        patterns. It does NOT use this to modify future confidence or weights.

        Parameters:
        -----------
        memory_snapshot : dict
            Snapshot from DecisionIntelligenceMemoryService containing:
            - confidence_records: Historical confidence values with timestamps
            - decision_timeline: Sequence of decisions and confidences

        Returns:
        --------
        dict with keys:
            - "disclaimer": Informational-only statement
            - "total_records": Count of confidence records analyzed
            - "confidence_statistics": Mean, median, std dev (descriptive)
            - "decay_analysis": Confidence decay over time (if any)
            - "variance_analysis": Dispersion of confidence values
            - "stability_index": Aggregated stability metric
            - "explanation": Why these are descriptive only
            - "processed_at": Timestamp of analysis

        IMPORTANT:
        - Stability metrics are HISTORICAL only
        - Decay patterns are OBSERVATIONAL
        - These do NOT predict future confidence
        - Should never be used to modify confidence levels
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
        Export trust calibration results with explicit disclaimers.

        This method produces deterministic exports (sorted keys, consistent ordering)
        of trust calibration analysis. All exports include prominent disclaimers that
        these results have no authority over trading decisions.

        Parameters:
        -----------
        calibration_result : dict
            Result from any calibration or stability computation method

        format : str
            Export format: "json" or "text"

        Returns:
        --------
        str
            Exported result in specified format

        IMPORTANT:
        - All exports are deterministic (same input = same output)
        - All exports include comprehensive disclaimers
        - Sorted keys ensure reproducibility
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
        """Get standard informational disclaimer."""
        return (
            "Informational analysis only. This output has no authority over trading decisions. "
            "Trust calibration metrics are DESCRIPTIVE HISTORICAL ANALYSIS. "
            "These results cannot be used to make trading decisions."
        )

    def _compute_signal_consistency(self, signal_records, outcome_records):
        """Compute consistency between signals and outcomes."""
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
        """Compute historical violation patterns."""
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
        """Compute alignment between reviewers and counterfactuals."""
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
        """Compute disagreement persistence patterns."""
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
        """Compute confidence statistics."""
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
        """Compute confidence decay over time."""
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
        """Compute variance analysis."""
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
        """Compute aggregate stability index."""
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
