"""
Decision Intelligence Memory Service (Phase 7)

Pure informational memory analysis service. Transforms archived intelligence 
reports into institutional memory for trend detection, pattern analysis, and 
human review.

CRITICAL CONSTRAINTS (DO NOT VIOLATE):
- NO execution logic
- NO enforcement logic
- NO orchestration
- NO trade blocking
- NO mutation of archived data
- NO database writes
- NO learning or adaptive behavior
- READ-ONLY: Only analyzes data, never modifies

PURPOSE:
- Transform archived intelligence into actionable institutional memory
- Detect trends and patterns in decision-making
- Compare temporal windows
- Provide human-readable memory snapshots

ARCHITECTURE:
- Pure read-only analysis layer
- All computations are deterministic
- All outputs deepcopied
- Fail-silent error handling
- Zero side effects

SAFETY GUARANTEES:
1. Append-only archive protection: Never modifies archive
2. Deterministic outputs: Same input always produces same result
3. Deepcopy on access: Returned data cannot affect service state
4. Fail-silent behavior: Graceful degradation on errors
5. No mutation: Internal state never changes during analysis
6. Informational only: All output is for human review only
7. Zero enforcement: No keywords or logic for enforcement

All methods are read-only and produce only informational output.
No execution, enforcement, blocking, or orchestration capabilities exist.
"""

import logging
import json
from datetime import datetime, timezone
from copy import deepcopy
from typing import Dict, Any, List, Optional
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class DecisionIntelligenceMemoryService:
    """
    Pure informational memory analysis service for archived decision intelligence.
    
    Transforms archived intelligence reports into institutional memory through:
    - Trend computation and analysis
    - Pattern detection in decision sequences
    - Temporal window comparisons
    - Memory snapshots for human review
    
    CRITICAL: This service is READ-ONLY and produces informational output only.
    No execution, enforcement, or modification capabilities exist.
    """

    def __init__(self):
        """
        Initialize memory service.
        
        State:
        - _cached_reports: List of archived reports loaded from archive service
                          (populated by external call to load_from_archive)
        
        All computation methods operate on _cached_reports and produce
        no side effects.
        """
        self._cached_reports: List[Dict[str, Any]] = []
        
        logger.info("DecisionIntelligenceMemoryService initialized (read-only)")

    def load_from_archive(self, reports: List[Dict[str, Any]]) -> None:
        """
        Load reports from DecisionIntelligenceArchiveService.
        
        This is the ONLY write operation allowed, and it only loads
        data for analysis. Never modifies the archive itself.
        
        Args:
            reports: List of archived decision intelligence reports
        
        Returns:
            None (fail-silent on errors)
        """
        try:
            if not isinstance(reports, list):
                logger.debug("Invalid reports type provided")
                return
            
            # Deepcopy to prevent external modifications
            self._cached_reports = deepcopy(reports)
            logger.debug(f"Loaded {len(self._cached_reports)} reports for analysis")
            
        except Exception as e:
            logger.exception(f"Error loading reports from archive: {e}")
            # Fail-silent: continue without raising

    def compute_trends(self, time_window: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Compute trends across archived reports.
        
        Analyzes:
        - Confidence score distribution (avg, min, max)
        - Governance pressure distribution
        - Risk flag frequency
        - Trade volume patterns
        
        Args:
            time_window: Optional dict with 'start' and 'end' timestamps
                        for filtering reports (if None, uses all reports)
        
        Returns:
            Dict with trend analysis (deepcopied, safe for external modification)
        
        Note:
            - Returns empty structure on empty archive (never raises)
            - All calculations are deterministic
            - All numbers are informational only
        """
        try:
            if not self._cached_reports:
                return self._empty_trends_structure()
            
            # Filter by time window if provided
            reports_to_analyze = self._filter_by_time_window(
                self._cached_reports, time_window
            )
            
            if not reports_to_analyze:
                return self._empty_trends_structure()
            
            # Extract values safely
            confidence_scores = []
            governance_pressures = []
            risk_flags_all = {}
            trade_volumes = []
            
            for report in reports_to_analyze:
                try:
                    # Confidence score
                    conf = report.get("confidence_score")
                    if isinstance(conf, (int, float)) and 0 <= conf <= 1:
                        confidence_scores.append(conf)
                    
                    # Governance pressure
                    gov = report.get("governance_pressure")
                    if isinstance(gov, (int, float)) and 0 <= gov <= 1:
                        governance_pressures.append(gov)
                    
                    # Risk flags frequency
                    flags = report.get("risk_flags", [])
                    if isinstance(flags, list):
                        for flag in flags:
                            if isinstance(flag, str):
                                risk_flags_all[flag] = risk_flags_all.get(flag, 0) + 1
                    
                    # Trade volume
                    volume = report.get("trade_volume")
                    if isinstance(volume, (int, float)) and volume >= 0:
                        trade_volumes.append(volume)
                
                except Exception as e:
                    logger.debug(f"Error extracting values from report: {e}")
                    continue
            
            # Build trends structure
            trends = {
                "metadata": {
                    "report_count": len(reports_to_analyze)
                },
                "confidence": self._compute_statistics(confidence_scores),
                "governance_pressure": self._compute_statistics(governance_pressures),
                "risk_flag_frequency": risk_flags_all,
                "trade_volume": self._compute_statistics(trade_volumes),
                "disclaimer": "This trend analysis is informational only and does not influence live decisions."
            }
            
            return deepcopy(trends)
        
        except Exception as e:
            logger.exception(f"Error computing trends: {e}")
            return self._empty_trends_structure()

    def detect_patterns(self) -> Dict[str, Any]:
        """
        Detect patterns in decision sequences.
        
        Analyzes:
        - Repeated governance violations
        - Confidence decay sequences
        - Counterfactual regret clustering
        
        Args:
            None (operates on loaded reports)
        
        Returns:
            Dict with detected patterns (deepcopied)
        
        Note:
            - Returns empty structure on insufficient data (never raises)
            - Patterns are informational observations only
            - No action recommendations generated
        """
        try:
            if not self._cached_reports or len(self._cached_reports) < 2:
                return self._empty_patterns_structure()
            
            patterns = {
                "metadata": {
                    "report_count": len(self._cached_reports)
                },
                "repeated_violations": [],
                "confidence_decay_sequences": [],
                "regret_clusters": [],
                "disclaimer": "These patterns are informational observations only and do not trigger any actions."
            }
            
            # Detect repeated violations
            violation_counts = {}
            for report in self._cached_reports:
                risk_flags = report.get("risk_flags", [])
                if "REPEATED_VIOLATION" in risk_flags:
                    corr_id = report.get("correlation_id")
                    if corr_id:
                        violation_counts[corr_id] = violation_counts.get(corr_id, 0) + 1
            
            patterns["repeated_violations"] = [
                {
                    "correlation_id": cid,
                    "violation_count": count,
                    "observation": f"Repeated violation pattern observed ({count} occurrences)"
                }
                for cid, count in violation_counts.items()
                if count > 0
            ]
            
            # Detect confidence decay sequences
            confidence_sequence = []
            for report in self._cached_reports:
                conf = report.get("confidence_score")
                if isinstance(conf, (int, float)):
                    confidence_sequence.append({
                        "correlation_id": report.get("correlation_id"),
                        "confidence": conf
                    })
            
            if len(confidence_sequence) >= 3:
                # Find decreasing sequences of 3+ items
                for i in range(len(confidence_sequence) - 2):
                    seq = confidence_sequence[i:i+3]
                    if (seq[0]["confidence"] > seq[1]["confidence"] >
                        seq[2]["confidence"]):
                        patterns["confidence_decay_sequences"].append({
                            "start_index": i,
                            "correlation_ids": [s["correlation_id"] for s in seq],
                            "confidence_values": [s["confidence"] for s in seq],
                            "observation": "Confidence decay sequence detected"
                        })
            
            # Detect regret clustering
            regret_values = []
            regret_with_id = []
            for report in self._cached_reports:
                regret = report.get("counterfactual_regret")
                if isinstance(regret, (int, float)) and 0 <= regret <= 1:
                    regret_values.append(regret)
                    regret_with_id.append({
                        "correlation_id": report.get("correlation_id"),
                        "regret": regret
                    })
            
            if len(regret_values) >= 3:
                try:
                    avg_regret = mean(regret_values)
                    std_regret = stdev(regret_values) if len(regret_values) > 1 else 0
                    
                    # Cluster high-regret items (within 1 std of high end)
                    if std_regret > 0:
                        threshold = avg_regret + std_regret
                    else:
                        threshold = avg_regret * 1.5 if avg_regret > 0 else 0.5
                    
                    high_regret = [
                        item for item in regret_with_id
                        if item["regret"] >= threshold
                    ]
                    
                    if high_regret:
                        patterns["regret_clusters"].append({
                            "cluster_type": "high_regret",
                            "count": len(high_regret),
                            "average_regret": avg_regret,
                            "cluster_members": high_regret,
                            "observation": f"Cluster of {len(high_regret)} high-regret decisions"
                        })
                
                except Exception as e:
                    logger.debug(f"Error computing regret statistics: {e}")
            
            return deepcopy(patterns)
        
        except Exception as e:
            logger.exception(f"Error detecting patterns: {e}")
            return self._empty_patterns_structure()

    def compare_windows(
        self,
        window_a: List[Dict[str, Any]],
        window_b: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare two temporal windows of reports.
        
        Provides directional comparison only (improving vs degrading).
        NO scoring, NO recommendations.
        
        Args:
            window_a: First window of reports (earlier period)
            window_b: Second window of reports (later period)
        
        Returns:
            Dict showing directional changes (deepcopied)
        
        Note:
            - Purely directional (improving, degrading, stable)
            - No numeric scores or recommendations
            - No action suggestions generated
        """
        try:
            if not window_a or not window_b:
                return {
                    "status": "insufficient_data",
                    "comparison": None,
                    "disclaimer": "Insufficient data for comparison"
                }
            
            # Compute statistics for each window
            window_a_stats = self._compute_window_statistics(window_a)
            window_b_stats = self._compute_window_statistics(window_b)
            
            # Determine directional changes (informational only)
            comparison = {
                "metadata": {
                    "window_a_count": len(window_a),
                    "window_b_count": len(window_b)
                },
                "confidence_direction": self._determine_direction(
                    window_a_stats.get("confidence_avg"),
                    window_b_stats.get("confidence_avg")
                ),
                "governance_pressure_direction": self._determine_direction(
                    window_a_stats.get("governance_avg"),
                    window_b_stats.get("governance_avg")
                ),
                "risk_flag_trend": self._determine_direction(
                    window_a_stats.get("risk_count"),
                    window_b_stats.get("risk_count")
                ),
                "window_a_metrics": {
                    "avg_confidence": window_a_stats.get("confidence_avg"),
                    "avg_governance_pressure": window_a_stats.get("governance_avg"),
                    "total_risk_flags": window_a_stats.get("risk_count")
                },
                "window_b_metrics": {
                    "avg_confidence": window_b_stats.get("confidence_avg"),
                    "avg_governance_pressure": window_b_stats.get("governance_avg"),
                    "total_risk_flags": window_b_stats.get("risk_count")
                },
                "disclaimer": "This comparison is informational only and does not influence decisions."
            }
            
            return deepcopy(comparison)
        
        except Exception as e:
            logger.exception(f"Error comparing windows: {e}")
            return {
                "status": "error",
                "comparison": None,
                "disclaimer": "Error during comparison"
            }

    def export_memory_snapshot(self) -> Dict[str, Any]:
        """
        Export complete memory snapshot for review.
        
        Provides:
        - Timestamp and metadata
        - Summary statistics
        - Pattern analysis
        - Trend information
        - Human-readable and machine-readable format
        
        Args:
            None (operates on loaded reports)
        
        Returns:
            Dict with complete memory snapshot (deepcopied)
        
        Note:
            - Deterministic output
            - Includes explicit disclaimer
            - Never raises exception
        """
        try:
            snapshot = {
                "metadata": {
                    "report_count": len(self._cached_reports),
                    "service_name": "DecisionIntelligenceMemoryService"
                },
                "summary": {
                    "total_reports_analyzed": len(self._cached_reports),
                    "time_span": self._compute_time_span(),
                    "data_completeness": self._assess_completeness()
                },
                "snapshot_data": {
                    "trends": self.compute_trends(),
                    "patterns": self.detect_patterns()
                },
                "disclaimer": (
                    "INFORMATIONAL ONLY: This memory snapshot is generated for human "
                    "review and analysis only. It does not influence live decisions or "
                    "trigger any enforcement actions. All statistics are historical "
                    "observations only."
                )
            }
            
            return deepcopy(snapshot)
        
        except Exception as e:
            logger.exception(f"Error exporting memory snapshot: {e}")
            return {
                "status": "error",
                "metadata": {
                    "service_name": "DecisionIntelligenceMemoryService"
                },
                "disclaimer": "Error during snapshot export"
            }

    # ========== Helper Methods (All Deterministic, No Side Effects) ==========

    def _compute_statistics(self, values: List[float]) -> Dict[str, Any]:
        """
        Compute basic statistics (avg, min, max, count).
        
        Args:
            values: List of numeric values
        
        Returns:
            Dict with statistics or empty structure
        
        Note:
            Deterministic and fails silently on invalid input.
        """
        try:
            if not values or not all(isinstance(v, (int, float)) for v in values):
                return {
                    "count": 0,
                    "avg": None,
                    "min": None,
                    "max": None
                }
            
            return {
                "count": len(values),
                "avg": mean(values),
                "min": min(values),
                "max": max(values)
            }
        except Exception as e:
            logger.debug(f"Error computing statistics: {e}")
            return {"count": 0, "avg": None, "min": None, "max": None}

    def _filter_by_time_window(
        self,
        reports: List[Dict[str, Any]],
        time_window: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter reports by time window (if provided).
        
        Args:
            reports: List of reports to filter
            time_window: Dict with 'start' and 'end' timestamps or None
        
        Returns:
            Filtered list (or original if no window provided)
        
        Note:
            Fails silently if time window is invalid.
        """
        try:
            if not time_window:
                return reports
            
            start = time_window.get("start")
            end = time_window.get("end")
            
            if not start or not end:
                return reports
            
            filtered = []
            for report in reports:
                try:
                    timestamp = report.get("timestamp")
                    if start <= timestamp <= end:
                        filtered.append(report)
                except Exception:
                    continue
            
            return filtered if filtered else reports
        
        except Exception as e:
            logger.debug(f"Error filtering by time window: {e}")
            return reports

    def _determine_direction(
        self,
        value_a: Optional[float],
        value_b: Optional[float]
    ) -> str:
        """
        Determine directional change between two values.
        
        Args:
            value_a: First value
            value_b: Second value
        
        Returns:
            String: "improving", "degrading", "stable", or "unknown"
        
        Note:
            Purely informational direction indicator.
        """
        try:
            if value_a is None or value_b is None:
                return "unknown"
            
            if not isinstance(value_a, (int, float)) or not isinstance(value_b, (int, float)):
                return "unknown"
            
            difference = abs(value_b - value_a)
            threshold = 0.01  # 1% threshold for "stable"
            
            if difference < threshold:
                return "stable"
            elif value_b > value_a:
                return "improving"
            else:
                return "degrading"
        
        except Exception:
            return "unknown"

    def _compute_window_statistics(
        self,
        window: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute statistics for a window of reports.
        
        Args:
            window: List of reports
        
        Returns:
            Dict with computed statistics
        """
        try:
            if not window:
                return {}
            
            confidence_scores = []
            governance_pressures = []
            risk_count = 0
            
            for report in window:
                try:
                    conf = report.get("confidence_score")
                    if isinstance(conf, (int, float)):
                        confidence_scores.append(conf)
                    
                    gov = report.get("governance_pressure")
                    if isinstance(gov, (int, float)):
                        governance_pressures.append(gov)
                    
                    flags = report.get("risk_flags", [])
                    if isinstance(flags, list):
                        risk_count += len(flags)
                
                except Exception:
                    continue
            
            return {
                "confidence_avg": mean(confidence_scores) if confidence_scores else None,
                "governance_avg": mean(governance_pressures) if governance_pressures else None,
                "risk_count": risk_count
            }
        
        except Exception as e:
            logger.debug(f"Error computing window statistics: {e}")
            return {}

    def _compute_time_span(self) -> str:
        """
        Compute time span of loaded reports.
        
        Returns:
            String description of time span
        """
        try:
            if not self._cached_reports:
                return "No data"
            
            timestamps = []
            for report in self._cached_reports:
                ts = report.get("timestamp")
                if ts:
                    timestamps.append(ts)
            
            if len(timestamps) >= 2:
                return f"From {min(timestamps)} to {max(timestamps)}"
            elif timestamps:
                return f"Single timestamp: {timestamps[0]}"
            else:
                return "No timestamps"
        
        except Exception:
            return "Unable to determine"

    def _assess_completeness(self) -> float:
        """
        Assess completeness of loaded data (0.0 to 1.0).
        
        Returns:
            Float representing data completeness
        """
        try:
            if not self._cached_reports:
                return 0.0
            
            required_fields = [
                "correlation_id", "confidence_score", "governance_pressure"
            ]
            
            complete_count = 0
            for report in self._cached_reports:
                if all(field in report for field in required_fields):
                    complete_count += 1
            
            return complete_count / len(self._cached_reports)
        
        except Exception:
            return 0.0

    def _empty_trends_structure(self) -> Dict[str, Any]:
        """
        Return empty trends structure (for empty archive).
        
        Returns:
            Dict with empty trends
        """
        return {
            "metadata": {
                "report_count": 0
            },
            "confidence": {
                "count": 0,
                "avg": None,
                "min": None,
                "max": None
            },
            "governance_pressure": {
                "count": 0,
                "avg": None,
                "min": None,
                "max": None
            },
            "risk_flag_frequency": {},
            "trade_volume": {
                "count": 0,
                "avg": None,
                "min": None,
                "max": None
            },
            "disclaimer": "This trend analysis is informational only and does not influence live decisions."
        }

    def _empty_patterns_structure(self) -> Dict[str, Any]:
        """
        Return empty patterns structure (for insufficient data).
        
        Returns:
            Dict with empty patterns
        """
        return {
            "metadata": {
                "report_count": len(self._cached_reports)
            },
            "repeated_violations": [],
            "confidence_decay_sequences": [],
            "regret_clusters": [],
            "disclaimer": "These patterns are informational observations only and do not trigger any actions."
        }
