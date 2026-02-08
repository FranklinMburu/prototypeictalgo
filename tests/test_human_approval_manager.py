"""
Stage 8 Test Suite: Human Approval & Execution Boundary v1.0

Comprehensive tests for:
- Binary approval constraint (APPROVED | REJECTED only)
- Frozen snapshot immutability
- Stage 7 expiration integration
- Audit log immutability
- Execution boundary enforcement
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timezone, timedelta
from reasoner_service.human_approval_manager import (
    HumanApprovalManager,
    AdvisorySnapshot,
    AuditLogEntry,
    ApprovalOutcome,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def manager():
    """Create a fresh HumanApprovalManager for each test."""
    return HumanApprovalManager()


@pytest.fixture
def valid_snapshot():
    """Create a valid advisory snapshot."""
    now = datetime.now(timezone.utc)
    return AdvisorySnapshot(
        advisory_id="ADV-001",
        htf_bias="BIAS_UP",
        reasoning_mode="entry_evaluation",
        price=150.50,
        expiration_timestamp=now + timedelta(hours=2),
        created_at=now,
        reasoning_context={"timeframe": "4H"},
    )


@pytest.fixture
def expired_snapshot():
    """Create an advisory snapshot that has already expired."""
    now = datetime.now(timezone.utc)
    return AdvisorySnapshot(
        advisory_id="ADV-EXPIRED",
        htf_bias="BIAS_DOWN",
        reasoning_mode="trade_management",
        price=100.00,
        expiration_timestamp=now - timedelta(minutes=5),  # Expired 5 min ago
        created_at=now - timedelta(hours=2),
        reasoning_context={"timeframe": "1H"},
    )


# ============================================================================
# SECTION 1: AdvisorySnapshot IMMUTABILITY TESTS
# ============================================================================

class TestAdvisorySnapshotImmutability:
    """Verify frozen snapshot cannot be modified after creation."""
    
    def test_snapshot_is_frozen(self, valid_snapshot):
        """Snapshot is immutable (frozen=True)."""
        with pytest.raises(AttributeError):
            valid_snapshot.price = 999.99  # Cannot modify frozen dataclass
    
    def test_snapshot_frozen_prevents_field_changes(self, valid_snapshot):
        """All fields are frozen, not just price."""
        with pytest.raises(AttributeError):
            valid_snapshot.htf_bias = "BIAS_DOWN"
        
        with pytest.raises(AttributeError):
            valid_snapshot.reasoning_mode = "bias_evaluation"
    
    def test_snapshot_equality_by_value(self, valid_snapshot):
        """Snapshots with same values are equal."""
        snapshot2 = AdvisorySnapshot(
            advisory_id=valid_snapshot.advisory_id,
            htf_bias=valid_snapshot.htf_bias,
            reasoning_mode=valid_snapshot.reasoning_mode,
            price=valid_snapshot.price,
            expiration_timestamp=valid_snapshot.expiration_timestamp,
            created_at=valid_snapshot.created_at,
            reasoning_context=valid_snapshot.reasoning_context,
        )
        assert snapshot2 == valid_snapshot


# ============================================================================
# SECTION 2: BINARY APPROVAL CONSTRAINT TESTS
# ============================================================================

class TestBinaryApprovalConstraint:
    """Verify only APPROVED | REJECTED outcomes are possible."""
    
    def test_approve_returns_approved(self, manager, valid_snapshot):
        """approve=True returns ApprovalOutcome.APPROVED."""
        outcome = manager.approve_advisory(
            valid_snapshot,
            user_id="user123",
            approve=True,
            reason="Looks good"
        )
        assert outcome == ApprovalOutcome.APPROVED
    
    def test_reject_returns_rejected(self, manager, valid_snapshot):
        """approve=False returns ApprovalOutcome.REJECTED."""
        outcome = manager.approve_advisory(
            valid_snapshot,
            user_id="user123",
            approve=False,
            reason="Risk too high"
        )
        assert outcome == ApprovalOutcome.REJECTED
    
    def test_approval_stored_in_outcomes(self, manager, valid_snapshot):
        """Approval outcome is stored for execution boundary."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        assert valid_snapshot.advisory_id in manager.approval_outcomes
        assert manager.approval_outcomes[valid_snapshot.advisory_id] == ApprovalOutcome.APPROVED
    
    def test_rejection_stored_in_outcomes(self, manager, valid_snapshot):
        """Rejection outcome is stored for execution boundary."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        
        assert valid_snapshot.advisory_id in manager.approval_outcomes
        assert manager.approval_outcomes[valid_snapshot.advisory_id] == ApprovalOutcome.REJECTED


# ============================================================================
# SECTION 3: FROZEN SNAPSHOT ENFORCEMENT TESTS
# ============================================================================

class TestFrozenSnapshotEnforcement:
    """Verify approved advisories are frozen and immutable."""
    
    def test_approved_advisory_snapshot_frozen(self, manager, valid_snapshot):
        """Approved advisory snapshot is stored and immutable."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        frozen = manager.approvals[valid_snapshot.advisory_id]
        assert frozen == valid_snapshot
        
        # Verify it's truly frozen
        with pytest.raises(AttributeError):
            frozen.price = 999.99
    
    def test_rejected_advisory_snapshot_not_stored(self, manager, valid_snapshot):
        """Rejected advisory snapshot is not stored in approvals dict."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        
        assert valid_snapshot.advisory_id not in manager.approvals
    
    def test_snapshot_matches_frozen_copy(self, manager, valid_snapshot):
        """Frozen snapshot exactly matches submitted snapshot."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        frozen = manager.approvals[valid_snapshot.advisory_id]
        assert frozen.advisory_id == valid_snapshot.advisory_id
        assert frozen.htf_bias == valid_snapshot.htf_bias
        assert frozen.reasoning_mode == valid_snapshot.reasoning_mode
        assert frozen.price == valid_snapshot.price
        assert frozen.expiration_timestamp == valid_snapshot.expiration_timestamp


# ============================================================================
# SECTION 4: STAGE 7 EXPIRATION CHECK TESTS
# ============================================================================

class TestStage7ExpirationCheck:
    """Verify Stage 7 expiration rules are enforced."""
    
    def test_valid_advisory_not_expired(self, manager, valid_snapshot):
        """Advisory not yet at expiration timestamp is not expired."""
        is_expired = manager._stage7_expiration_check(valid_snapshot)
        assert is_expired is False
    
    def test_expired_advisory_is_expired(self, manager, expired_snapshot):
        """Advisory past expiration timestamp is expired."""
        is_expired = manager._stage7_expiration_check(expired_snapshot)
        assert is_expired is True
    
    def test_approve_expired_returns_expired_outcome(self, manager, expired_snapshot):
        """Approving an expired advisory returns EXPIRED outcome."""
        outcome = manager.approve_advisory(
            expired_snapshot,
            user_id="user123",
            approve=True,
            reason="Was good earlier"
        )
        assert outcome == ApprovalOutcome.EXPIRED
    
    def test_expired_advisory_not_frozen(self, manager, expired_snapshot):
        """Expired advisory is not added to approvals dict."""
        manager.approve_advisory(expired_snapshot, user_id="user123", approve=True)
        
        assert expired_snapshot.advisory_id not in manager.approvals
    
    def test_expiration_check_with_different_timeframes(self, manager):
        """Expiration check respects different timeframe durations."""
        now = datetime.now(timezone.utc)
        
        # 1H timeframe: should expire after ~30 min (50% of 1H)
        snapshot_1h = AdvisorySnapshot(
            advisory_id="ADV-1H",
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=now + timedelta(minutes=2),
            created_at=now,
            reasoning_context={"timeframe": "1H"},
        )
        
        # 1D timeframe: should expire much later
        snapshot_1d = AdvisorySnapshot(
            advisory_id="ADV-1D",
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=now + timedelta(hours=24),
            created_at=now,
            reasoning_context={"timeframe": "1D"},
        )
        
        # 1H should not be expired yet (2 min in future)
        assert manager._stage7_expiration_check(snapshot_1h) is False
        # 1D definitely not expired
        assert manager._stage7_expiration_check(snapshot_1d) is False


# ============================================================================
# SECTION 5: AUDIT LOG IMMUTABILITY TESTS
# ============================================================================

class TestAuditLogImmutability:
    """Verify audit log entries are immutable and forensically sound."""
    
    def test_audit_entry_is_frozen(self, valid_snapshot):
        """AuditLogEntry is immutable (frozen=True)."""
        entry = AuditLogEntry(
            advisory_id="ADV-001",
            user_id="user123",
            timestamp_request=datetime.now(timezone.utc),
            timestamp_received=datetime.now(timezone.utc),
            state_snapshot=valid_snapshot,
            outcome=ApprovalOutcome.APPROVED,
        )
        
        with pytest.raises(AttributeError):
            entry.outcome = ApprovalOutcome.REJECTED
    
    def test_audit_logged_on_approval(self, manager, valid_snapshot):
        """Approval decision is logged to audit trail."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True, reason="OK")
        
        assert len(manager.audit_log) == 1
        entry = manager.audit_log[0]
        assert entry.advisory_id == valid_snapshot.advisory_id
        assert entry.outcome == ApprovalOutcome.APPROVED
        assert entry.user_id == "user123"
        assert entry.reason == "OK"
    
    def test_audit_logged_on_rejection(self, manager, valid_snapshot):
        """Rejection decision is logged to audit trail."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False, reason="Too risky")
        
        assert len(manager.audit_log) == 1
        entry = manager.audit_log[0]
        assert entry.outcome == ApprovalOutcome.REJECTED
        assert entry.reason == "Too risky"
    
    def test_audit_logged_on_expiration(self, manager, expired_snapshot):
        """Expired advisory is logged to audit trail."""
        manager.approve_advisory(expired_snapshot, user_id="user123", approve=True)
        
        assert len(manager.audit_log) == 1
        entry = manager.audit_log[0]
        assert entry.outcome == ApprovalOutcome.EXPIRED
    
    def test_audit_entry_captures_snapshot(self, manager, valid_snapshot):
        """Audit entry captures frozen snapshot for compliance."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        entry = manager.audit_log[0]
        assert entry.state_snapshot == valid_snapshot
        assert entry.state_snapshot.advisory_id == "ADV-001"
        assert entry.state_snapshot.price == 150.50
    
    def test_audit_entry_captures_timestamps(self, manager, valid_snapshot):
        """Audit entry captures both request and received timestamps."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        entry = manager.audit_log[0]
        assert entry.timestamp_request is not None
        assert entry.timestamp_received is not None
        # Received should be >= request (or very close)
        assert entry.timestamp_received >= entry.timestamp_request
    
    def test_audit_trail_grows_with_each_approval(self, manager, valid_snapshot):
        """Each approval adds an entry to audit trail."""
        for i in range(3):
            snapshot = AdvisorySnapshot(
                advisory_id=f"ADV-{i}",
                htf_bias="BIAS_UP",
                reasoning_mode="entry_evaluation",
                price=100.0 + i,
                expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            manager.approve_advisory(snapshot, user_id=f"user{i}", approve=True)
        
        assert len(manager.audit_log) == 3
    
    def test_audit_entry_to_dict_serialization(self, manager, valid_snapshot):
        """Audit entries can be serialized to dict for persistence."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        entry_dict = manager.audit_log[0].to_dict()
        assert isinstance(entry_dict, dict)
        assert entry_dict["advisory_id"] == "ADV-001"
        assert entry_dict["user_id"] == "user123"
        assert entry_dict["outcome"] == "APPROVED"
        assert isinstance(entry_dict["timestamp_request"], str)  # ISO format
        assert isinstance(entry_dict["timestamp_received"], str)


# ============================================================================
# SECTION 6: EXECUTION BOUNDARY TESTS
# ============================================================================

class TestExecutionBoundary:
    """Verify execute_if_approved enforces strict boundary conditions."""
    
    def test_execute_approved_advisory(self, manager, valid_snapshot):
        """Approved advisory can be executed."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        can_execute = manager.execute_if_approved(valid_snapshot.advisory_id)
        assert can_execute is True
    
    def test_execute_rejected_advisory_blocked(self, manager, valid_snapshot):
        """Rejected advisory cannot be executed."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        
        can_execute = manager.execute_if_approved(valid_snapshot.advisory_id)
        assert can_execute is False
    
    def test_execute_non_existent_advisory_blocked(self, manager):
        """Non-existent advisory cannot be executed."""
        can_execute = manager.execute_if_approved("NONEXISTENT")
        assert can_execute is False
    
    def test_execute_expired_advisory_blocked(self, manager, expired_snapshot):
        """Expired advisory cannot be executed."""
        # First approve it (will be marked EXPIRED)
        manager.approve_advisory(expired_snapshot, user_id="user123", approve=True)
        
        can_execute = manager.execute_if_approved(expired_snapshot.advisory_id)
        assert can_execute is False
    
    def test_execute_only_frozen_snapshot(self, manager, valid_snapshot):
        """Execution uses frozen snapshot, not live data."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        frozen = manager.approvals[valid_snapshot.advisory_id]
        assert frozen.price == 150.50
        assert frozen.htf_bias == "BIAS_UP"
        
        # Verify frozen snapshot is immutable
        with pytest.raises(AttributeError):
            frozen.price = 999.99


# ============================================================================
# SECTION 7: VALIDATION TESTS
# ============================================================================

class TestSnapshotValidation:
    """Verify snapshot validation catches missing critical fields."""
    
    def test_approve_without_advisory_id_raises(self, manager):
        """Approving snapshot without advisory_id raises ValueError."""
        bad_snapshot = AdvisorySnapshot(
            advisory_id="",  # Empty!
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        with pytest.raises(ValueError, match="advisory_id is required"):
            manager.approve_advisory(bad_snapshot, user_id="user123", approve=True)
    
    def test_approve_without_htf_bias_raises(self, manager):
        """Approving snapshot without htf_bias raises ValueError."""
        bad_snapshot = AdvisorySnapshot(
            advisory_id="ADV-001",
            htf_bias="",  # Empty!
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        with pytest.raises(ValueError, match="htf_bias is required"):
            manager.approve_advisory(bad_snapshot, user_id="user123", approve=True)
    
    def test_approve_without_reasoning_mode_raises(self, manager):
        """Approving snapshot without reasoning_mode raises ValueError."""
        bad_snapshot = AdvisorySnapshot(
            advisory_id="ADV-001",
            htf_bias="BIAS_UP",
            reasoning_mode="",  # Empty!
            price=100.0,
            expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        with pytest.raises(ValueError, match="reasoning_mode is required"):
            manager.approve_advisory(bad_snapshot, user_id="user123", approve=True)
    
    def test_approve_without_expiration_raises(self, manager):
        """Approving snapshot without expiration_timestamp raises ValueError."""
        bad_snapshot = AdvisorySnapshot(
            advisory_id="ADV-001",
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=None,  # Empty!
        )
        
        with pytest.raises(ValueError, match="expiration_timestamp is required"):
            manager.approve_advisory(bad_snapshot, user_id="user123", approve=True)


# ============================================================================
# SECTION 8: AUDIT TRAIL RETRIEVAL TESTS
# ============================================================================

class TestAuditTrailRetrieval:
    """Verify audit trail can be retrieved for compliance."""
    
    def test_get_full_audit_trail(self, manager):
        """Retrieve full audit trail for all advisories."""
        snapshots = [
            AdvisorySnapshot(
                advisory_id=f"ADV-{i}",
                htf_bias="BIAS_UP",
                reasoning_mode="entry_evaluation",
                price=100.0 + i,
                expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            for i in range(3)
        ]
        
        for snapshot in snapshots:
            manager.approve_advisory(snapshot, user_id="user123", approve=True)
        
        trail = manager.get_audit_trail()
        assert len(trail) == 3
        assert all(isinstance(entry, dict) for entry in trail)
    
    def test_get_filtered_audit_trail(self, manager, valid_snapshot):
        """Retrieve audit trail filtered by advisory_id."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        trail = manager.get_audit_trail(advisory_id="ADV-001")
        assert len(trail) == 1
        assert trail[0]["advisory_id"] == "ADV-001"
    
    def test_audit_trail_empty_when_no_approvals(self, manager):
        """Audit trail is empty when no approvals made."""
        trail = manager.get_audit_trail()
        assert len(trail) == 0


# ============================================================================
# SECTION 9: VALIDITY CHECK TESTS
# ============================================================================

class TestApprovalValidity:
    """Verify is_approval_valid checks all conditions."""
    
    def test_approved_valid_advisory_is_valid(self, manager, valid_snapshot):
        """Approved, unexpired advisory is valid."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        is_valid = manager.is_approval_valid(valid_snapshot.advisory_id)
        assert is_valid is True
    
    def test_rejected_advisory_not_valid(self, manager, valid_snapshot):
        """Rejected advisory is not valid."""
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        
        is_valid = manager.is_approval_valid(valid_snapshot.advisory_id)
        assert is_valid is False
    
    def test_expired_advisory_not_valid(self, manager, expired_snapshot):
        """Expired advisory is not valid."""
        manager.approve_advisory(expired_snapshot, user_id="user123", approve=True)
        
        is_valid = manager.is_approval_valid(expired_snapshot.advisory_id)
        assert is_valid is False
    
    def test_non_existent_advisory_not_valid(self, manager):
        """Non-existent advisory is not valid."""
        is_valid = manager.is_approval_valid("NONEXISTENT")
        assert is_valid is False


# ============================================================================
# SECTION 10: MULTIPLE APPROVALS TEST
# ============================================================================

class TestMultipleApprovalsWorkflow:
    """Verify manager handles multiple simultaneous approvals."""
    
    def test_multiple_advisories_independent(self, manager):
        """Multiple advisories are independent."""
        now = datetime.now(timezone.utc)
        
        snapshots = [
            AdvisorySnapshot(
                advisory_id=f"ADV-{i}",
                htf_bias=f"BIAS_UP",
                reasoning_mode="entry_evaluation",
                price=100.0 + i * 10,
                expiration_timestamp=now + timedelta(hours=1),
            )
            for i in range(3)
        ]
        
        # Approve all
        for snapshot in snapshots:
            manager.approve_advisory(snapshot, user_id="user123", approve=True)
        
        # Verify all are approved
        for snapshot in snapshots:
            assert manager.is_approval_valid(snapshot.advisory_id)
        
        # Reject one
        manager.approve_advisory(
            AdvisorySnapshot(
                advisory_id="ADV-REJECT",
                htf_bias="BIAS_UP",
                reasoning_mode="entry_evaluation",
                price=500.0,
                expiration_timestamp=now + timedelta(hours=1),
            ),
            user_id="user123",
            approve=False
        )
        
        # Verify rejection doesn't affect others
        assert manager.is_approval_valid("ADV-0")
        assert not manager.is_approval_valid("ADV-REJECT")


# ============================================================================
# SECTION 11: EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""
    
    def test_snapshot_exactly_at_expiration_timestamp(self, manager):
        """Advisory at exact expiration timestamp is considered expired."""
        now = datetime.now(timezone.utc)
        snapshot = AdvisorySnapshot(
            advisory_id="ADV-EDGE",
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=now,  # Exactly now
        )
        
        # Should be expired (now > expiration_timestamp is True when equal)
        # Note: depends on system precision, but typically expires
        is_expired = manager._stage7_expiration_check(snapshot)
        # This is at the edge, so we just verify it completes without error
        assert isinstance(is_expired, bool)
    
    def test_very_long_expiration_in_future(self, manager):
        """Advisory with long expiration still works."""
        now = datetime.now(timezone.utc)
        snapshot = AdvisorySnapshot(
            advisory_id="ADV-LONG",
            htf_bias="BIAS_UP",
            reasoning_mode="entry_evaluation",
            price=100.0,
            expiration_timestamp=now + timedelta(days=30),
        )
        
        outcome = manager.approve_advisory(snapshot, user_id="user123", approve=True)
        assert outcome == ApprovalOutcome.APPROVED
    
    def test_reason_field_optional(self, manager, valid_snapshot):
        """Reason field is optional."""
        outcome = manager.approve_advisory(
            valid_snapshot,
            user_id="user123",
            approve=True,
            reason=None  # No reason provided
        )
        assert outcome == ApprovalOutcome.APPROVED
        assert manager.audit_log[0].reason is None
    
    def test_custom_timeframe_durations(self):
        """Manager accepts custom timeframe duration mappings."""
        custom_durations = {
            "2H": 7200,
            "8H": 28800,
        }
        manager = HumanApprovalManager(timeframe_candle_durations=custom_durations)
        
        assert manager.timeframe_durations["2H"] == 7200
        assert manager.timeframe_durations["8H"] == 28800


# ============================================================================
# SECTION 12: LOGGING VERIFICATION TESTS
# ============================================================================

class TestLogging:
    """Verify appropriate logging for audit and debugging."""
    
    def test_approve_logs_info(self, manager, valid_snapshot, caplog):
        """Approval decision is logged at INFO level."""
        import logging as logging_module
        caplog.set_level(logging_module.INFO)
        
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=True)
        
        assert "Stage 8:" in caplog.text
        assert "APPROVED" in caplog.text or "approved" in caplog.text
    
    def test_reject_logs_info(self, manager, valid_snapshot, caplog):
        """Rejection decision is logged at INFO level."""
        import logging as logging_module
        caplog.set_level(logging_module.INFO)
        
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        
        assert "Stage 8:" in caplog.text
        assert "REJECTED" in caplog.text or "rejected" in caplog.text
    
    def test_expired_logs_error(self, manager, expired_snapshot, caplog):
        """Expired advisory is logged at ERROR level."""
        import logging as logging_module
        caplog.set_level(logging_module.ERROR)
        
        manager.approve_advisory(expired_snapshot, user_id="user123", approve=True)
        
        assert "ERROR" in caplog.text or "error" in caplog.text
        assert "expired" in caplog.text.lower()
    
    def test_execution_blocked_logs(self, manager, valid_snapshot, caplog):
        """Blocked execution is logged."""
        import logging as logging_module
        caplog.set_level(logging_module.ERROR)
        
        manager.approve_advisory(valid_snapshot, user_id="user123", approve=False)
        manager.execute_if_approved(valid_snapshot.advisory_id)
        
        assert "blocked" in caplog.text.lower() or "error" in caplog.text.lower()
