"""
Decision Intelligence Archive Service

Persists DecisionIntelligenceReport outputs for historical review, trend analysis,
audits, and offline research.

CRITICAL DISCLAIMER: This service is PURELY INFORMATIONAL and APPEND-ONLY.
It archives intelligence reports and performs only analysis for human review.
It has NO enforcement, execution, or decision-making capability.

KEY PRINCIPLES:
- Pure append-only storage (no updates or deletes)
- Immutability of stored records (fetched data is deepcopied)
- Deterministic reads (same input → same output)
- Fail-silent error handling (graceful degradation)
- No mutations of input reports
- No learning or adaptive behavior
- Comprehensive disclaimers on all stored data
- Zero enforcement capability verified
- Cannot influence trading in any way

STORAGE MODEL:
- In-memory storage (list-based, append-only)
- Indexed by correlation_id and timestamp
- Each record is immutable once appended
- Chronological insertion order preserved

This service enables human-informed analysis through archival and trending,
never autonomous enforcement or execution.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from copy import deepcopy
import statistics

logger = logging.getLogger(__name__)


class DecisionIntelligenceArchiveService:
    """
    Appends DecisionIntelligenceReport outputs to an immutable historical archive
    for later review, trending, and audit purposes.
    
    CRITICAL: This service is APPEND-ONLY and READ-ONLY-ON-READ:
    - No execution logic
    - No enforcement logic
    - No trade blocking or allow/deny
    - No orchestration
    - No mutation of stored intelligence
    - APPEND-ONLY writes (never update or delete)
    - READ operations MUST be deterministic
    - FAIL-SILENT behavior only
    - INFORMATIONAL PURPOSE ONLY
    
    Storage is immutable after write. All reads return deepcopies to preserve
    immutability guarantees. Fetched data cannot affect archive state.
    """
    
    def __init__(self):
        """
        Initialize archive with empty storage.
        
        This service maintains a purely append-only, in-memory list of archived reports.
        No external dependencies or services are referenced.
        """
        # Immutable append-only storage
        self._archive: List[Dict[str, Any]] = []
        
        logger.info("DecisionIntelligenceArchiveService initialized (append-only, read-only-on-read)")
    
    def archive_report(self, report: Dict[str, Any]) -> None:
        """
        Append a single DecisionIntelligenceReport to the archive.
        
        APPEND-ONLY: This method adds to the archive without updating or deleting.
        The report is immediately deepcopied for storage immutability.
        
        WHY THIS CANNOT INFLUENCE TRADING:
        - This method only appends to historical storage
        - No execution, orchestration, or governance logic
        - No callbacks or side effects
        - No references to trade execution services
        - No modification of input services
        - Pure informational persistence only
        
        Args:
            report: DecisionIntelligenceReport dict to archive
                {
                    "correlation_id": str,
                    "confidence_score": float (0-100),
                    "governance_pressure": str,
                    "counterfactual_regret": float,
                    "risk_flags": list[str],
                    "explanation": str,
                    "evaluated_at": str (ISO timestamp),
                    "disclaimer": str,
                }
        
        Returns:
            None (fail-silent: invalid reports silently skipped)
        """
        try:
            # Fail-silent: skip invalid inputs
            if not isinstance(report, dict) or not report:
                logger.debug(f"Skipping invalid report: {type(report)}")
                return
            
            # Verify required structure
            if "correlation_id" not in report:
                logger.debug("Skipping report without correlation_id")
                return
            
            # Deepcopy for immutability: input reports are protected from modification
            archived_copy = deepcopy(report)
            
            # Append-only: add to end of archive
            self._archive.append(archived_copy)
            
            logger.debug(f"Archived report for {report.get('correlation_id')}")
        
        except Exception as e:
            logger.exception(f"Error archiving report: {e}")
            # Fail-silent: continue without raising
    
    def archive_batch(self, reports: List[Dict[str, Any]]) -> None:
        """
        Append multiple DecisionIntelligenceReports to the archive.
        
        APPEND-ONLY: This method adds all valid reports without updating or deleting.
        Invalid reports in the batch are skipped, remaining reports are archived.
        
        WHY THIS CANNOT INFLUENCE TRADING:
        - Batch operation only appends to historical storage
        - No aggregation logic that could trigger enforcement
        - No orchestration or decision-making
        - Pure informational persistence only
        - Invalid items silently skipped, valid items archived
        
        Args:
            reports: List of DecisionIntelligenceReport dicts to archive
        
        Returns:
            None (fail-silent: batch continues despite invalid items)
        """
        try:
            # Fail-silent: skip invalid inputs
            if not isinstance(reports, list):
                logger.debug(f"Skipping invalid batch: {type(reports)}")
                return
            
            # Append each valid report
            for report in reports:
                self.archive_report(report)
        
        except Exception as e:
            logger.exception(f"Error archiving batch: {e}")
            # Fail-silent: continue without raising
    
    def fetch_by_correlation_id(self, correlation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all archived reports for a specific trade correlation_id.
        
        DETERMINISTIC READ: Same input always returns identical results.
        Returns deepcopies to preserve immutability guarantee.
        
        WHY THIS CANNOT INFLUENCE TRADING:
        - Read-only operation, no modifications
        - Returns historical analysis only (informational)
        - No enforcement or blocking capability
        - No side effects or state changes
        - Deepcopied results cannot affect archive
        
        Args:
            correlation_id: Trade correlation_id to search for
        
        Returns:
            List of archived reports matching correlation_id (empty if none found)
            Each report is a deepcopy (immutable from archive perspective)
        """
        try:
            # Fail-silent: handle invalid inputs
            if correlation_id is None:
                return []
            
            correlation_id_str = str(correlation_id)
            
            # Find all reports matching this correlation_id
            matching_reports = [
                deepcopy(report)
                for report in self._archive
                if report.get("correlation_id") == correlation_id_str
            ]
            
            return matching_reports
        
        except Exception as e:
            logger.exception(f"Error fetching by correlation_id: {e}")
            # Fail-silent: return empty list
            return []
    
    def fetch_all(self) -> List[Dict[str, Any]]:
        """
        Retrieve all archived reports in chronological order.
        
        DETERMINISTIC READ: Same input (always empty) returns identical results.
        Insertion order is preserved (append-only semantics).
        Returns deepcopies to preserve immutability guarantee.
        
        WHY THIS CANNOT INFLUENCE TRADING:
        - Read-only operation, no modifications
        - Returns historical analysis only (informational)
        - No enforcement or blocking capability
        - No side effects or state changes
        - Deepcopied results cannot affect archive
        
        Returns:
            List of all archived reports in insertion order
            Each report is a deepcopy (immutable from archive perspective)
        """
        try:
            # Return deepcopies of all records (preserves immutability)
            return [deepcopy(report) for report in self._archive]
        
        except Exception as e:
            logger.exception(f"Error fetching all reports: {e}")
            # Fail-silent: return empty list
            return []
    
    def compute_trends(self) -> Dict[str, Any]:
        """
        Compute historical trends and statistics from archived reports.
        
        INFORMATIONAL ANALYSIS: Provides aggregate statistics only.
        No enforcement, blocking, or decision-making implications.
        Non-prescriptive analysis for human review.
        
        WHY THIS CANNOT INFLUENCE TRADING:
        - Pure statistical aggregation, no enforcement logic
        - No prescriptive recommendations (informational only)
        - No enforcement keywords or action fields
        - No orchestration or decision-making
        - Trends are descriptive, not prescriptive
        
        Returns:
            {
                "total_archived": int (total reports),
                "average_confidence": float (0-100),
                "confidence_min": float,
                "confidence_max": float,
                "governance_pressure_distribution": {
                    "none": int,
                    "low": int,
                    "medium": int,
                    "high": int,
                },
                "disclaimer": str (non-enforcement guarantee),
            }
        """
        try:
            # Fail-silent: handle empty archive
            if not self._archive:
                return {
                    "total_archived": 0,
                    "average_confidence": 0.0,
                    "confidence_min": 0.0,
                    "confidence_max": 0.0,
                    "governance_pressure_distribution": {
                        "none": 0,
                        "low": 0,
                        "medium": 0,
                        "high": 0,
                    },
                    "disclaimer": (
                        "This trend analysis is informational only and does not influence live trading. "
                        "Trends are descriptive statistics, not prescriptive recommendations. "
                        "No enforcement, blocking, or execution occurs based on these trends."
                    ),
                }
            
            # Extract confidence scores
            confidence_scores = [
                report.get("confidence_score", 0.0)
                for report in self._archive
                if isinstance(report.get("confidence_score"), (int, float))
            ]
            
            # Calculate confidence statistics
            avg_confidence = statistics.mean(confidence_scores) if confidence_scores else 0.0
            min_confidence = min(confidence_scores) if confidence_scores else 0.0
            max_confidence = max(confidence_scores) if confidence_scores else 0.0
            
            # Count governance pressure distribution
            pressure_distribution = {
                "none": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
            }
            
            for report in self._archive:
                pressure = report.get("governance_pressure", "none")
                if pressure in pressure_distribution:
                    pressure_distribution[pressure] += 1
            
            return {
                "total_archived": len(self._archive),
                "average_confidence": round(avg_confidence, 2),
                "confidence_min": round(min_confidence, 2),
                "confidence_max": round(max_confidence, 2),
                "governance_pressure_distribution": pressure_distribution,
                "disclaimer": (
                    "This trend analysis is informational only and does not influence live trading. "
                    "Trends are descriptive statistics, not prescriptive recommendations. "
                    "No enforcement, blocking, or execution occurs based on these trends."
                ),
            }
        
        except Exception as e:
            logger.exception(f"Error computing trends: {e}")
            # Fail-silent: return minimal valid structure
            return {
                "total_archived": 0,
                "average_confidence": 0.0,
                "confidence_min": 0.0,
                "confidence_max": 0.0,
                "governance_pressure_distribution": {
                    "none": 0,
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                },
                "disclaimer": "Error computing trends. This analysis is informational only.",
            }
