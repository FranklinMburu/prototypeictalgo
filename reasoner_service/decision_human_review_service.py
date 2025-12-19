"""
Decision Human Review Service (Phase 9)

Pure human-in-the-loop review layer that allows humans to annotate and review
decisions without any execution, enforcement, learning, or feedback effects.

CRITICAL CONSTRAINTS (DO NOT VIOLATE):
- NO trade execution
- NO trade blocking
- NO policy enforcement
- NO memory mutation
- NO intelligence mutation
- NO learning or optimization
- NO orchestration
- NO writing to external services

ALLOWED OPERATIONS:
- Append-only review records
- Deterministic outputs
- Deepcopy all returned data
- Fail-silent error handling
- Informational/observational only

PURPOSE:
Enable human review and annotation of trading decisions for:
- Post-hoc analysis and learning
- Validation of decision-making process
- Documentation of human judgment
- Compliance and audit trails
- Pattern recognition for future policy development

INTEGRATION:
- Reads from: DecisionTimelineService (decision history)
- Reads from: TradeGovernanceService (governance context)
- Reads from: OutcomeAnalyticsService (trade outcomes)
- Reads from: DecisionIntelligenceMemoryService (memory analysis)
- Reads from: DecisionOfflineEvaluationService (policy scenarios)
- Writes to: NOTHING (human reviews only, never persisted back)

ARCHITECTURE:
- Pure append-only review storage
- All computations are deterministic
- All outputs deepcopied for protection
- Fail-silent error handling
- Zero side effects on any external service
- Human input is observational only (never influences system behavior)

SAFETY GUARANTEES:
1. Append-only storage: Reviews never deleted or updated, only appended
2. No upstream mutation: Archive, memory, intelligence services untouched
3. Deterministic outputs: Same input always produces same result
4. Deepcopy on read: Returned data cannot affect service state
5. Fail-silent behavior: Graceful degradation on errors
6. No learning: Human reviews never influence future decisions
7. No enforcement: Human annotations cannot block/allow trades
8. Informational only: All output is for audit/analysis purposes only

All methods are append-only and produce only informational output.
No execution, enforcement, blocking, or orchestration capabilities exist.
Human reviews have zero system authority.
"""

import logging
import json
import hashlib
from datetime import datetime, timezone
from copy import deepcopy
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    """Status of a review session."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DisagreementSeverity(Enum):
    """Severity level of disagreement with system decision."""
    MINOR = "minor"          # Small issue, outcome acceptable
    MODERATE = "moderate"    # Significant concern, rethinking needed
    SEVERE = "severe"        # Critical issue, immediate review needed
    CATASTROPHIC = "catastrophic"  # System failure, severe consequences


class DecisionHumanReviewService:
    """
    Pure human-in-the-loop review layer for trading decisions.
    
    Enables humans to:
    - Create review sessions for decision contexts
    - Attach annotations and observations
    - Record disagreements with reasoning
    - Export comprehensive review logs
    
    CRITICAL GUARANTEES:
    - All reviews are append-only
    - Zero influence on live trading decisions
    - No mutation of any upstream services
    - All outputs are informational only
    - Human input never affects system behavior
    - Reviews have zero system authority
    """

    def __init__(self):
        """
        Initialize human review service.
        
        State:
        - _review_sessions: Dict[session_id] -> review session record
        - _annotations: Dict[session_id] -> list of annotations (append-only)
        - _disagreements: Dict[session_id] -> list of disagreements (append-only)
        - _all_reviews: List of all review records (chronological)
        
        All storage is append-only in-memory. No persistence to external services.
        Human input is observational only and never affects system behavior.
        """
        self._review_sessions: Dict[str, Dict[str, Any]] = {}
        self._annotations: Dict[str, List[Dict[str, Any]]] = {}
        self._disagreements: Dict[str, List[Dict[str, Any]]] = {}
        self._all_reviews: List[Dict[str, Any]] = []
        
        logger.info("DecisionHumanReviewService initialized (append-only, human-observational)")

    def create_review_session(self, context_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new human review session for a decision context.
        
        This creates an append-only review record. It never modifies any
        upstream services and has zero influence on trading decisions.
        
        Args:
            context_snapshot: Context dict describing the decision
                {
                    "correlation_id": str,  # Trade/decision identifier
                    "decision_type": str,   # "entry" | "exit" | "hold"
                    "symbol": str,          # Trading symbol
                    "timestamp": str,       # ISO timestamp of decision
                    "original_decision": {  # Original system decision
                        "recommendation": str,
                        "confidence": float,
                        "reasoning": str,
                    },
                    "trade_outcome": {      # Actual outcome (if available)
                        "entry_price": float,
                        "exit_price": float,
                        "pnl": float,
                        "status": str,
                    },
                    "governance_context": {  # Governance at decision time
                        "active_rules": list[str],
                        "risk_flags": list[str],
                    },
                }
        
        Returns:
            Dict with review session (deepcopied, safe for external use)
            {
                "session_id": str,
                "correlation_id": str,
                "created_at": str (ISO),
                "created_by": str,  # System-generated, not user input
                "status": str,
                "context_snapshot": {...},  # Deepcopy of input
                "disclaimer": str,
            }
        
        Note:
            - Returns informational record, never influences decisions
            - Session ID is deterministic and collision-free
            - Fail-silent: Returns empty session on errors
            - All data is append-only
        """
        try:
            if not isinstance(context_snapshot, dict):
                logger.debug("Invalid context snapshot type")
                return self._empty_session()
            
            correlation_id = context_snapshot.get("correlation_id", "unknown")
            session_id = self._generate_session_id(correlation_id)
            
            session = {
                "session_id": session_id,
                "correlation_id": correlation_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",  # Never from user input
                "status": ReviewStatus.CREATED.value,
                "context_snapshot": deepcopy(context_snapshot),
                "annotation_count": 0,
                "disagreement_count": 0,
                "disclaimer": (
                    "This review session is for human analysis and audit purposes only. "
                    "Reviews have zero system authority and do not influence trading decisions. "
                    "All human input is observational and non-binding."
                ),
            }
            
            # Append to storage (append-only)
            self._review_sessions[session_id] = deepcopy(session)
            self._annotations[session_id] = []
            self._disagreements[session_id] = []
            
            # Add to chronological record
            self._all_reviews.append({
                "type": "session_created",
                "session_id": session_id,
                "timestamp": session["created_at"],
                "data": deepcopy(session),
            })
            
            logger.info(f"Created review session {session_id} for {correlation_id}")
            
            return deepcopy(session)
        
        except Exception as e:
            logger.exception(f"Error creating review session: {e}")
            return self._empty_session()

    def attach_annotation(
        self,
        session_id: str,
        annotation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attach a human annotation to a review session.
        
        Annotations are human observations that are NEVER used to:
        - Influence trading decisions
        - Modify archives or memory
        - Learn or optimize system behavior
        - Enforce policies or rules
        
        Args:
            session_id: ID of review session
            annotation: Annotation dict
                {
                    "annotator": str,           # Human identifier (not trusted)
                    "annotation_type": str,     # "observation" | "question" | "concern" | "praise"
                    "text": str,                # Annotation text
                    "relevant_fields": list[str],  # Which decision fields this addresses
                    "confidence_in_view": float,   # 0-1, annotator's confidence
                }
        
        Returns:
            Dict with annotation record (deepcopied, safe for external use)
            {
                "annotation_id": str,
                "session_id": str,
                "attached_at": str (ISO),
                "annotator": str,  # Original value preserved
                "annotation_type": str,
                "text": str,
                "relevant_fields": list[str],
                "confidence_in_view": float,
                "disclaimer": str,
            }
        
        Note:
            - Append-only: Never deletes or modifies existing annotations
            - Fail-silent: Invalid annotations logged but don't raise
            - Never influences any system behavior
            - All data deepcopied for protection
        """
        try:
            if session_id not in self._review_sessions:
                logger.debug(f"Session {session_id} not found")
                return self._empty_annotation(session_id)
            
            if not isinstance(annotation, dict):
                logger.debug("Invalid annotation type")
                return self._empty_annotation(session_id)
            
            annotation_id = self._generate_annotation_id(session_id)
            
            annotation_record = {
                "annotation_id": annotation_id,
                "session_id": session_id,
                "attached_at": datetime.now(timezone.utc).isoformat(),
                "annotator": annotation.get("annotator", "unknown"),
                "annotation_type": annotation.get("annotation_type", "observation"),
                "text": annotation.get("text", ""),
                "relevant_fields": annotation.get("relevant_fields", []),
                "confidence_in_view": max(0.0, min(1.0, annotation.get("confidence_in_view", 0.5))),
                "disclaimer": (
                    "This annotation is a human observation and has zero system authority. "
                    "It does not and cannot influence trading decisions or system behavior."
                ),
            }
            
            # Append to session's annotations (append-only)
            self._annotations[session_id].append(deepcopy(annotation_record))
            
            # Update session count
            if session_id in self._review_sessions:
                self._review_sessions[session_id]["annotation_count"] += 1
                self._review_sessions[session_id]["status"] = ReviewStatus.IN_PROGRESS.value
            
            # Add to chronological record
            self._all_reviews.append({
                "type": "annotation_attached",
                "session_id": session_id,
                "timestamp": annotation_record["attached_at"],
                "data": deepcopy(annotation_record),
            })
            
            logger.info(f"Attached annotation {annotation_id} to session {session_id}")
            
            return deepcopy(annotation_record)
        
        except Exception as e:
            logger.exception(f"Error attaching annotation: {e}")
            return self._empty_annotation(session_id)

    def record_disagreement(
        self,
        session_id: str,
        disagreement: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record a human disagreement with a system decision.
        
        Disagreements are logged observations that are NEVER used to:
        - Modify the original decision
        - Learn or retrain decision logic
        - Enforce policy changes
        - Block or allow future trades
        - Influence any system behavior
        
        Args:
            session_id: ID of review session
            disagreement: Disagreement dict
                {
                    "disagreer": str,           # Human identifier (not trusted)
                    "severity": str,            # "minor" | "moderate" | "severe" | "catastrophic"
                    "reason": str,              # Why human disagrees
                    "alternative_decision": str,  # What human would have done
                    "pnl_impact": float,        # Estimated P&L if human decision taken
                }
        
        Returns:
            Dict with disagreement record (deepcopied, safe for external use)
            {
                "disagreement_id": str,
                "session_id": str,
                "recorded_at": str (ISO),
                "disagreer": str,
                "severity": str,
                "reason": str,
                "alternative_decision": str,
                "pnl_impact": float,
                "disclaimer": str,
            }
        
        Note:
            - Append-only: Never deletes or modifies disagreements
            - Fail-silent: Invalid disagreements logged but don't raise
            - Never influences any system behavior or future decisions
            - Severity is informational (not used to trigger actions)
            - All data deepcopied for protection
        """
        try:
            if session_id not in self._review_sessions:
                logger.debug(f"Session {session_id} not found")
                return self._empty_disagreement(session_id)
            
            if not isinstance(disagreement, dict):
                logger.debug("Invalid disagreement type")
                return self._empty_disagreement(session_id)
            
            disagreement_id = self._generate_disagreement_id(session_id)
            
            # Validate severity
            severity_str = disagreement.get("severity", "moderate")
            try:
                severity = DisagreementSeverity[severity_str.upper()].value
            except (KeyError, AttributeError):
                severity = DisagreementSeverity.MODERATE.value
            
            disagreement_record = {
                "disagreement_id": disagreement_id,
                "session_id": session_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "disagreer": disagreement.get("disagreer", "unknown"),
                "severity": severity,
                "reason": disagreement.get("reason", ""),
                "alternative_decision": disagreement.get("alternative_decision", ""),
                "pnl_impact": float(disagreement.get("pnl_impact", 0.0)) if disagreement.get("pnl_impact") else 0.0,
                "disclaimer": (
                    "This disagreement is a human observation and has zero system authority. "
                    "It does not and cannot influence trading decisions, learning, or future system behavior. "
                    "Severity is informational only and never triggers automatic enforcement."
                ),
            }
            
            # Append to session's disagreements (append-only)
            self._disagreements[session_id].append(deepcopy(disagreement_record))
            
            # Update session count
            if session_id in self._review_sessions:
                self._review_sessions[session_id]["disagreement_count"] += 1
                self._review_sessions[session_id]["status"] = ReviewStatus.IN_PROGRESS.value
            
            # Add to chronological record
            self._all_reviews.append({
                "type": "disagreement_recorded",
                "session_id": session_id,
                "timestamp": disagreement_record["recorded_at"],
                "data": deepcopy(disagreement_record),
            })
            
            logger.info(f"Recorded disagreement {disagreement_id} to session {session_id}")
            
            return deepcopy(disagreement_record)
        
        except Exception as e:
            logger.exception(f"Error recording disagreement: {e}")
            return self._empty_disagreement(session_id)

    def summarize_reviews(self) -> Dict[str, Any]:
        """
        Summarize all human reviews collected so far.
        
        This produces an informational summary for human analysis purposes only.
        It never influences any system behavior or decision-making.
        
        Returns:
            Dict with review summary (deepcopied, safe for external use)
            {
                "summary_generated_at": str (ISO),
                "total_sessions": int,
                "total_annotations": int,
                "total_disagreements": int,
                "sessions_by_status": {
                    "created": int,
                    "in_progress": int,
                    "completed": int,
                    "archived": int,
                },
                "disagreement_severity_distribution": {
                    "minor": int,
                    "moderate": int,
                    "severe": int,
                    "catastrophic": int,
                },
                "annotation_type_distribution": {
                    "observation": int,
                    "question": int,
                    "concern": int,
                    "praise": int,
                },
                "average_confidence_in_views": float,
                "total_pnl_impact_if_human_decisions": float,
                "explanation": str,
                "disclaimer": str,
                "is_deterministic": bool,
            }
        
        Note:
            - Deterministic: Same reviews produce same summary
            - Fail-silent: Returns empty summary on errors
            - All data deepcopied for protection
            - Summary is informational only, never triggers actions
        """
        try:
            # Count sessions by status
            sessions_by_status = {
                "created": sum(1 for s in self._review_sessions.values() if s.get("status") == ReviewStatus.CREATED.value),
                "in_progress": sum(1 for s in self._review_sessions.values() if s.get("status") == ReviewStatus.IN_PROGRESS.value),
                "completed": sum(1 for s in self._review_sessions.values() if s.get("status") == ReviewStatus.COMPLETED.value),
                "archived": sum(1 for s in self._review_sessions.values() if s.get("status") == ReviewStatus.ARCHIVED.value),
            }
            
            # Count disagreements by severity
            disagreement_severity_distribution = {
                "minor": 0,
                "moderate": 0,
                "severe": 0,
                "catastrophic": 0,
            }
            
            all_disagreements = []
            for disagreements in self._disagreements.values():
                all_disagreements.extend(disagreements)
            
            for disagreement in all_disagreements:
                severity = disagreement.get("severity", "moderate")
                if severity in disagreement_severity_distribution:
                    disagreement_severity_distribution[severity] += 1
            
            # Count annotations by type
            annotation_type_distribution = {
                "observation": 0,
                "question": 0,
                "concern": 0,
                "praise": 0,
            }
            
            all_annotations = []
            for annotations in self._annotations.values():
                all_annotations.extend(annotations)
            
            for annotation in all_annotations:
                ann_type = annotation.get("annotation_type", "observation")
                if ann_type in annotation_type_distribution:
                    annotation_type_distribution[ann_type] += 1
            
            # Calculate average confidence
            confidences = [a.get("confidence_in_view", 0.5) for a in all_annotations]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Calculate total P&L impact if human decisions were taken
            total_pnl_impact = sum(d.get("pnl_impact", 0.0) for d in all_disagreements)
            
            summary = {
                "summary_generated_at": datetime.now(timezone.utc).isoformat(),
                "total_sessions": len(self._review_sessions),
                "total_annotations": len(all_annotations),
                "total_disagreements": len(all_disagreements),
                "sessions_by_status": sessions_by_status,
                "disagreement_severity_distribution": disagreement_severity_distribution,
                "annotation_type_distribution": annotation_type_distribution,
                "average_confidence_in_views": round(avg_confidence, 4),
                "total_pnl_impact_if_human_decisions": round(total_pnl_impact, 2),
                "explanation": self._generate_summary_explanation(
                    len(self._review_sessions),
                    len(all_annotations),
                    len(all_disagreements),
                    total_pnl_impact
                ),
                "disclaimer": (
                    "This summary is for human analysis and audit purposes only. "
                    "It has zero system authority and does not influence trading decisions. "
                    "All figures are informational observations."
                ),
                "is_deterministic": True,
            }
            
            logger.info(f"Generated review summary with {summary['total_sessions']} sessions")
            
            return deepcopy(summary)
        
        except Exception as e:
            logger.exception(f"Error summarizing reviews: {e}")
            return self._empty_summary()

    def export_review_log(self, format: str = "json") -> str:
        """
        Export complete review log in deterministic format.
        
        The export is deterministic: identical reviews produce identical exports.
        It never influences any system behavior or decision-making.
        
        Args:
            format: Output format ("json" or "text")
        
        Returns:
            str: Formatted review log (deterministic, sorted)
        
        Note:
            - Deterministic: Same reviews always produce identical export
            - Sorted: Keys and records sorted for consistency
            - Includes comprehensive disclaimers
            - Fail-silent: Returns JSON error on format errors
        """
        try:
            # Build export data structure
            export_data = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "export_format": format,
                "total_sessions": len(self._review_sessions),
                "total_reviews": len(self._all_reviews),
                "sessions": {},
                "all_reviews_chronological": [],
            }
            
            # Add all sessions (sorted by ID)
            for session_id in sorted(self._review_sessions.keys()):
                session = self._review_sessions[session_id]
                annotations = self._annotations.get(session_id, [])
                disagreements = self._disagreements.get(session_id, [])
                
                export_data["sessions"][session_id] = {
                    "session": deepcopy(session),
                    "annotations": deepcopy(sorted(annotations, key=lambda a: a.get("attached_at", ""))),
                    "disagreements": deepcopy(sorted(disagreements, key=lambda d: d.get("recorded_at", ""))),
                }
            
            # Add all reviews in chronological order
            export_data["all_reviews_chronological"] = deepcopy(
                sorted(self._all_reviews, key=lambda r: r.get("timestamp", ""))
            )
            
            # Add export disclaimer
            export_data["export_disclaimer"] = (
                "This review log is for human analysis, audit, and compliance purposes only. "
                "Reviews have zero system authority and do not influence trading decisions. "
                "All human input is observational and non-binding. "
                "No reviews are used for learning, optimization, or enforcement."
            )
            
            if format.lower() == "text":
                return self._format_as_text(export_data)
            else:
                # Default to JSON (deterministic, sorted)
                return json.dumps(export_data, indent=2, sort_keys=True, default=str)
        
        except Exception as e:
            logger.exception(f"Error exporting review log: {e}")
            return json.dumps({
                "error": str(e),
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This review log is for human analysis only. "
                    "Reviews have zero system authority."
                ),
            }, indent=2, default=str)

    # ========== PRIVATE HELPER METHODS ==========

    def _generate_session_id(self, correlation_id: str) -> str:
        """Generate deterministic session ID."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            combined = f"{correlation_id}_{timestamp}"
            hash_digest = hashlib.md5(combined.encode()).hexdigest()
            return f"review_{hash_digest[:12]}"
        except Exception as e:
            logger.debug(f"Error generating session ID: {e}")
            return f"review_{len(self._review_sessions)}"

    def _generate_annotation_id(self, session_id: str) -> str:
        """Generate deterministic annotation ID."""
        try:
            count = len(self._annotations.get(session_id, []))
            combined = f"{session_id}_{count}_{datetime.now(timezone.utc).isoformat()}"
            hash_digest = hashlib.md5(combined.encode()).hexdigest()
            return f"annotation_{hash_digest[:12]}"
        except Exception as e:
            logger.debug(f"Error generating annotation ID: {e}")
            return f"annotation_{len(self._all_reviews)}"

    def _generate_disagreement_id(self, session_id: str) -> str:
        """Generate deterministic disagreement ID."""
        try:
            count = len(self._disagreements.get(session_id, []))
            combined = f"{session_id}_{count}_{datetime.now(timezone.utc).isoformat()}"
            hash_digest = hashlib.md5(combined.encode()).hexdigest()
            return f"disagreement_{hash_digest[:12]}"
        except Exception as e:
            logger.debug(f"Error generating disagreement ID: {e}")
            return f"disagreement_{len(self._all_reviews)}"

    def _generate_summary_explanation(
        self,
        session_count: int,
        annotation_count: int,
        disagreement_count: int,
        total_pnl_impact: float
    ) -> str:
        """Generate human-readable summary explanation."""
        try:
            explanation = (
                f"Review summary: {session_count} sessions created with "
                f"{annotation_count} annotations and {disagreement_count} disagreements recorded. "
                f"If all human disagreement decisions were taken, cumulative P&L impact would be {total_pnl_impact:.2f}. "
                f"This is informational analysis only and does not influence system behavior."
            )
            return explanation
        except Exception as e:
            logger.debug(f"Error generating explanation: {e}")
            return "Review summary generated. This is informational analysis only."

    def _format_as_text(self, export_data: Dict[str, Any]) -> str:
        """Format review log as human-readable text."""
        try:
            lines = [
                "=" * 80,
                "DECISION HUMAN REVIEW LOG",
                "=" * 80,
                "",
                f"Export Timestamp: {export_data.get('export_timestamp', 'N/A')}",
                f"Total Sessions: {export_data.get('total_sessions', 0)}",
                f"Total Reviews: {export_data.get('total_reviews', 0)}",
                "",
                "SESSIONS:",
            ]
            
            for session_id, session_data in export_data.get("sessions", {}).items():
                session = session_data.get("session", {})
                annotations = session_data.get("annotations", [])
                disagreements = session_data.get("disagreements", [])
                
                lines.append(f"\n  Session: {session_id}")
                lines.append(f"    Correlation ID: {session.get('correlation_id', 'N/A')}")
                lines.append(f"    Created: {session.get('created_at', 'N/A')}")
                lines.append(f"    Status: {session.get('status', 'N/A')}")
                lines.append(f"    Annotations: {len(annotations)}")
                lines.append(f"    Disagreements: {len(disagreements)}")
            
            lines.extend([
                "",
                "DISCLAIMERS:",
                export_data.get("export_disclaimer", "N/A"),
                "",
                "=" * 80,
            ])
            
            return "\n".join(lines)
        
        except Exception as e:
            logger.debug(f"Error formatting as text: {e}")
            return json.dumps(export_data, indent=2, default=str)

    def _empty_session(self) -> Dict[str, Any]:
        """Return empty session structure."""
        return {
            "session_id": "unknown",
            "correlation_id": "unknown",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "system",
            "status": ReviewStatus.CREATED.value,
            "context_snapshot": {},
            "annotation_count": 0,
            "disagreement_count": 0,
            "disclaimer": (
                "This review session is for human analysis only. "
                "Reviews have zero system authority."
            ),
        }

    def _empty_annotation(self, session_id: str) -> Dict[str, Any]:
        """Return empty annotation structure."""
        return {
            "annotation_id": "unknown",
            "session_id": session_id,
            "attached_at": datetime.now(timezone.utc).isoformat(),
            "annotator": "unknown",
            "annotation_type": "observation",
            "text": "",
            "relevant_fields": [],
            "confidence_in_view": 0.0,
            "disclaimer": (
                "This annotation has zero system authority."
            ),
        }

    def _empty_disagreement(self, session_id: str) -> Dict[str, Any]:
        """Return empty disagreement structure."""
        return {
            "disagreement_id": "unknown",
            "session_id": session_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "disagreer": "unknown",
            "severity": DisagreementSeverity.MODERATE.value,
            "reason": "",
            "alternative_decision": "",
            "pnl_impact": 0.0,
            "disclaimer": (
                "This disagreement has zero system authority."
            ),
        }

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "summary_generated_at": datetime.now(timezone.utc).isoformat(),
            "total_sessions": 0,
            "total_annotations": 0,
            "total_disagreements": 0,
            "sessions_by_status": {
                "created": 0,
                "in_progress": 0,
                "completed": 0,
                "archived": 0,
            },
            "disagreement_severity_distribution": {
                "minor": 0,
                "moderate": 0,
                "severe": 0,
                "catastrophic": 0,
            },
            "annotation_type_distribution": {
                "observation": 0,
                "question": 0,
                "concern": 0,
                "praise": 0,
            },
            "average_confidence_in_views": 0.0,
            "total_pnl_impact_if_human_decisions": 0.0,
            "explanation": "Empty summary.",
            "disclaimer": (
                "This summary is for human analysis only. "
                "Reviews have zero system authority."
            ),
            "is_deterministic": True,
        }
